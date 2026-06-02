#!/usr/bin/env python3
import hashlib
import http.client
import ipaddress
import json
import os
import socket
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit


DEFAULT_CLOUD_SERVER_URL = "https://api.knudg.com"
DEFAULT_CONFIG_PATH = Path(".codex") / "knudg" / "client-config.json"
LOCAL_AUTH_PROFILE = "local"
LOCAL_SERVER_ID = "local-dev"
LOCAL_LOOPBACK_DEPLOYMENT_TYPES = {"local", "greencloud_closed_launch"}
LOCAL_LOOPBACK_AUTH_PROFILES = {"local", "closed_launch_no_user_routes"}
LOCAL_CLOSED_LAUNCH_DNS_HOSTS = {"api.knudg.com"}
TAILSCALE_IPV4_NETWORK = ipaddress.ip_network("100.64.0.0/10")
TAILSCALE_IPV6_NETWORK = ipaddress.ip_network("fd7a:115c:a1e0::/48")
CONFIG_SCHEMA_VERSION = 1
CAPABILITIES_SCHEMA_VERSION = 1
API_VERSION = "v1"
PROFILES = {"local", "cloud", "enterprise"}
CALLER_CONTEXTS = {"cli", "mcp_once", "agent_wrapper"}
EXPLORATION_DEPTHS = {"off", "hard", "harder"}
SECRET_KEY_PARTS = {"secret", "token", "password", "credential", "api_key", "apikey", "private_key"}
PROBE_PATHS = {"/health/live", "/health/startup", "/health/ready", "/capabilities"}


class ConfigError(ValueError):
    pass


class CapabilitiesInvalid(ConfigError):
    pass


class HealthInvalid(ConfigError):
    pass


class ProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class EffectiveProfile:
    profile: str
    server_url: str
    auth_profile: str
    tenant_id: None
    pin_state: str
    pin: dict | None
    config_path: Path


@dataclass(frozen=True)
class ClientConfig:
    active_profile: str
    profiles: dict
    pins: dict
    capabilities_cache: dict
    exploration_depth: str
    path: Path

    def to_dict(self):
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "active_profile": self.active_profile,
            "profiles": self.profiles,
            "pins": self.pins,
            "capabilities_cache": self.capabilities_cache,
            "exploration_depth": self.exploration_depth,
        }


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_config(path=None):
    return ClientConfig(
        active_profile="cloud",
        profiles={
            "cloud": {
                "server_url": DEFAULT_CLOUD_SERVER_URL,
                "auth_profile": "cloud",
                "tenant_id": None,
            },
            "local": {
                "server_url": None,
                "auth_profile": LOCAL_AUTH_PROFILE,
                "tenant_id": None,
            },
            "enterprise": {
                "server_url": None,
                "auth_profile": "enterprise",
                "tenant_id": None,
            },
        },
        pins={},
        capabilities_cache={},
        exploration_depth="off",
        path=Path(path) if path is not None else DEFAULT_CONFIG_PATH,
    )


def config_path_from_env(env=None, override=None):
    if override:
        return Path(override)
    env = env or os.environ
    if env.get("KNUDG_CONFIG"):
        return Path(env["KNUDG_CONFIG"])
    return DEFAULT_CONFIG_PATH


def load_config(path=None, env=None):
    resolved = config_path_from_env(env=env, override=path)
    if not resolved.exists():
        return default_config(resolved)
    data = json.loads(resolved.read_text(encoding="utf-8"))
    validate_no_secret_fields(data)
    if not isinstance(data, dict) or data.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ConfigError("unsupported config schema")
    active_profile = data.get("active_profile", "cloud")
    if active_profile not in PROFILES:
        raise ConfigError("invalid active profile")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        raise ConfigError("profiles must be an object")
    pins = data.get("pins") or {}
    capabilities_cache = data.get("capabilities_cache") or {}
    if not isinstance(pins, dict) or not isinstance(capabilities_cache, dict):
        raise ConfigError("pins and capabilities_cache must be objects")
    exploration_depth = data.get("exploration_depth", "off")
    if exploration_depth not in EXPLORATION_DEPTHS:
        raise ConfigError("invalid exploration_depth")
    return ClientConfig(
        active_profile=active_profile,
        profiles={**default_config(resolved).profiles, **profiles},
        pins=pins,
        capabilities_cache=capabilities_cache,
        exploration_depth=exploration_depth,
        path=resolved,
    )


def _is_reparse_point(path):
    try:
        attrs = path.stat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _reject_unsafe_path(path):
    path = Path(path)
    if path.exists() and (path.is_symlink() or _is_reparse_point(path)):
        raise ConfigError("config path must not be a symlink or reparse point")
    parent = path.parent
    check = parent
    missing = []
    while not check.exists():
        missing.append(check)
        if check.parent == check:
            break
        check = check.parent
    while check != check.parent:
        if check.exists() and (check.is_symlink() or _is_reparse_point(check)):
            raise ConfigError("config parent path must not traverse a symlink or reparse point")
        check = check.parent
    for item in missing:
        if item.exists() and (item.is_symlink() or _is_reparse_point(item)):
            raise ConfigError("config parent path must not traverse a symlink or reparse point")


def save_config(config, path=None):
    target = Path(path) if path is not None else config.path
    validate_no_secret_fields(config.to_dict())
    _reject_unsafe_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.to_dict(), sort_keys=True, indent=2)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
        os.replace(tmp_name, target)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def validate_no_secret_fields(config):
    def walk(path, value):
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if any(part in lowered for part in SECRET_KEY_PARTS):
                    raise ConfigError(f"{path}.{key}: secret-like field is not allowed")
                walk(f"{path}.{key}", item)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(f"{path}[{index}]", item)

    walk("config", config)


def _split_port(split):
    try:
        return split.port
    except ValueError as exc:
        raise ConfigError("invalid server port") from exc


def normalize_server_url(url, profile):
    if profile not in PROFILES:
        raise ConfigError("invalid profile")
    if profile == "cloud":
        if url == DEFAULT_CLOUD_SERVER_URL:
            return DEFAULT_CLOUD_SERVER_URL
        raise ConfigError("cloud custom server is not configured")
    if profile == "enterprise":
        raise ConfigError("enterprise custom server is not configured")
    if not isinstance(url, str) or not url:
        raise ConfigError("server_url is required")
    try:
        split = urlsplit(url)
    except ValueError as exc:
        raise ConfigError("invalid server_url") from exc
    if split.scheme != "http":
        raise ConfigError("local server_url must use http")
    if split.username or split.password:
        raise ConfigError("server_url must not include userinfo")
    if split.query or split.fragment:
        raise ConfigError("server_url must not include query or fragment")
    if split.path not in ("", "/"):
        raise ConfigError("server_url must not include a path")
    hostname = split.hostname
    if not hostname:
        raise ConfigError("server_url host is required")
    if "%" in split.netloc or "%" in hostname or hostname.endswith("."):
        raise ConfigError("server_url host is not allowed")
    host = hostname.lower()
    if not is_loopback_host(host) and host not in LOCAL_CLOSED_LAUNCH_DNS_HOSTS:
        raise ConfigError("local server_url must be loopback or an allowed closed-launch DNS host")
    port = _split_port(split)
    if port is not None and (port < 1 or port > 65535):
        raise ConfigError("invalid server port")
    if host in LOCAL_CLOSED_LAUNCH_DNS_HOSTS and port not in {None, 80}:
        raise ConfigError("closed-launch DNS server_url must use the default HTTP port")
    normalized_host = f"[{host}]" if host == "::1" else host
    return f"http://{normalized_host}{':' + str(port) if port else ''}"


def _profile_entry(config, profile):
    entry = config.profiles.get(profile) or {}
    if profile == "cloud":
        return {"server_url": DEFAULT_CLOUD_SERVER_URL, "auth_profile": "cloud", "tenant_id": None, **entry}
    if profile == "local":
        return {"server_url": None, "auth_profile": LOCAL_AUTH_PROFILE, "tenant_id": None, **entry}
    return {"server_url": None, "auth_profile": "enterprise", "tenant_id": None, **entry}


def effective_profile(config, env=None, overrides=None, caller_context: Literal["cli", "mcp_once", "agent_wrapper"] = "cli"):
    if caller_context not in CALLER_CONTEXTS:
        raise ConfigError("invalid caller_context")
    env = env or {}
    overrides = overrides or {}
    profile = overrides.get("profile") or config.active_profile
    if profile not in PROFILES:
        raise ConfigError("invalid profile")
    entry = _profile_entry(config, profile)
    server_url = overrides.get("server_url") or entry.get("server_url")
    auth_profile = entry.get("auth_profile") or profile
    if caller_context == "cli":
        if env.get("KNUDG_SERVER_URL") and profile == "local":
            server_url = env["KNUDG_SERVER_URL"]
        if env.get("KNUDG_AUTH_PROFILE") and profile == "local":
            auth_profile = env["KNUDG_AUTH_PROFILE"]
    if profile == "local":
        server_url = normalize_server_url(server_url, "local")
    elif profile == "cloud":
        server_url = normalize_server_url(server_url, "cloud")
    else:
        raise ConfigError("enterprise custom server is not configured")
    pin = config.pins.get(profile)
    pin_state = "unpinned"
    if pin:
        pin_state = "pinned"
        if (
            pin.get("server_url") != server_url
            or pin.get("auth_profile") != auth_profile
            or pin.get("tenant_id") is not None
        ):
            pin_state = "override_unpinned"
    if overrides.get("server_url") or (caller_context == "cli" and env.get("KNUDG_SERVER_URL")):
        if pin_state != "unpinned":
            pin_state = "override_unpinned"
        elif pin is None:
            pin_state = "override_unpinned"
    return EffectiveProfile(
        profile=profile,
        server_url=server_url,
        auth_profile=auth_profile,
        tenant_id=None,
        pin_state=pin_state,
        pin=pin,
        config_path=config.path,
    )


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_capabilities_digest(capabilities):
    included = {
        "schema_version": capabilities.get("schema_version"),
        "server_id": capabilities.get("server_id"),
        "deployment_type": capabilities.get("deployment_type"),
        "api_version": capabilities.get("api_version"),
        "features": capabilities.get("features"),
        "policy_versions": capabilities.get("policy_versions"),
        "auth": capabilities.get("auth"),
    }
    return "sha256:" + hashlib.sha256(_canonical_json(included).encode("utf-8")).hexdigest()


def _loopback_origin_equivalent(capability_origin, expected_origin):
    try:
        capability = urlsplit(capability_origin)
        expected = urlsplit(expected_origin)
    except (TypeError, ValueError):
        return False
    if capability.username or capability.password or expected.username or expected.password:
        return False
    if capability.query or capability.fragment or expected.query or expected.fragment:
        return False
    if capability.path not in ("", "/") or expected.path not in ("", "/"):
        return False
    capability_host = (capability.hostname or "").lower()
    expected_host = (expected.hostname or "").lower()
    if capability_host != expected_host or capability.port != expected.port:
        return False
    if expected.scheme != "http" or capability.scheme not in {"http", "https"}:
        return False
    return is_loopback_host(capability_host) or capability_host in LOCAL_CLOSED_LAUNCH_DNS_HOSTS


def is_loopback_host(host):
    return host in {"localhost", "127.0.0.1", "::1"}


def _is_tailscale_ip(address):
    parsed = ipaddress.ip_address(address)
    return parsed in TAILSCALE_IPV4_NETWORK or parsed in TAILSCALE_IPV6_NETWORK


def validate_capabilities(capabilities, origin):
    if not isinstance(capabilities, dict):
        raise CapabilitiesInvalid("capabilities must be an object")
    if capabilities.get("schema_version") != CAPABILITIES_SCHEMA_VERSION:
        raise CapabilitiesInvalid("unsupported capabilities schema")
    if not isinstance(capabilities.get("server_id"), str) or not capabilities["server_id"]:
        raise CapabilitiesInvalid("capabilities server_id is required")
    if capabilities.get("deployment_type") not in LOCAL_LOOPBACK_DEPLOYMENT_TYPES:
        raise CapabilitiesInvalid("local loopback capabilities must declare an allowed deployment_type")
    if capabilities.get("api_version") != API_VERSION:
        raise CapabilitiesInvalid("unsupported api_version")
    if not _loopback_origin_equivalent(capabilities.get("capability_resource_origin"), origin):
        raise CapabilitiesInvalid("capability_resource_origin must match server origin")
    features = capabilities.get("features")
    if not isinstance(features, dict) or any(not isinstance(value, bool) for value in features.values()):
        raise CapabilitiesInvalid("capabilities features must be boolean flags")
    policy_versions = capabilities.get("policy_versions")
    if not isinstance(policy_versions, dict) or any(not isinstance(value, str) for value in policy_versions.values()):
        raise CapabilitiesInvalid("capabilities policy_versions must be strings")
    auth = capabilities.get("auth")
    if not isinstance(auth, dict) or auth.get("profile") not in LOCAL_LOOPBACK_AUTH_PROFILES:
        raise CapabilitiesInvalid("local loopback capabilities must use an allowed auth.profile")
    if auth.get("protected_resource_metadata_url") is not None:
        raise CapabilitiesInvalid("local loopback capabilities must not advertise protected_resource_metadata_url")
    if capabilities.get("deployment_type") != "local" and features.get("publication") is not False:
        raise CapabilitiesInvalid("closed launch loopback capabilities must keep publication disabled")
    return capabilities


def validate_ready_health(health):
    if not isinstance(health, dict):
        raise HealthInvalid("health must be an object")
    if health.get("status") not in {"ok", "ready"}:
        raise HealthInvalid("health status is not ready")
    components = health.get("components") or {}
    route_classes = health.get("route_classes") or {}
    if not isinstance(components, dict) or not isinstance(route_classes, dict):
        raise HealthInvalid("health components and route_classes must be objects")
    deployment_type = health.get("deployment_type", "local")
    if deployment_type == "local":
        if route_classes.get("search") != "disabled":
            raise HealthInvalid("local loopback readiness must keep search disabled")
        protected = {"trusted-consent-revocation", "reviewer-admin"}
        for route in protected:
            if route_classes.get(route) != "disabled":
                raise HealthInvalid("protected route classes must be disabled in local loopback readiness")
    elif deployment_type == "greencloud_closed_launch":
        if components.get("publication") != "disabled":
            raise HealthInvalid("closed launch readiness must keep publication disabled")
        if route_classes.get("landing") != "disabled" or route_classes.get("reviewer-admin") != "disabled":
            raise HealthInvalid("closed launch readiness must keep public/admin surfaces disabled")
    else:
        raise HealthInvalid("unsupported loopback deployment_type")
    return health


def _host_header(normalized):
    split = urlsplit(normalized)
    port = _split_port(split)
    host = split.hostname or ""
    display_host = f"[{host}]" if ":" in host else host
    return f"{display_host}:{port}" if port else display_host


def _resolve_allowed_local_server(host, port):
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_loopback and not _is_tailscale_ip(host):
            raise ProbeError("server host is not loopback or Tailscale")
        return host
    host = host.lower()
    infos = socket.getaddrinfo(host, port or 80, type=socket.SOCK_STREAM)
    addresses = []
    for info in infos:
        address = info[4][0]
        parsed = ipaddress.ip_address(address)
        if is_loopback_host(host):
            if not parsed.is_loopback:
                raise ProbeError("localhost resolved to a non-loopback address")
        elif host in LOCAL_CLOSED_LAUNCH_DNS_HOSTS:
            if not _is_tailscale_ip(address):
                raise ProbeError("closed-launch DNS host did not resolve to a Tailscale address")
        else:
            raise ProbeError("server host is not allowed")
        addresses.append(address)
    if not addresses:
        raise ProbeError("localhost did not resolve")
    for address in addresses:
        if ":" not in address:
            return address
    return addresses[0]


def probe_json(origin, path: Literal["/health/live", "/health/startup", "/health/ready", "/capabilities"], timeout_seconds=2.0, max_bytes=65536):
    if path not in PROBE_PATHS:
        raise ProbeError("probe path is not allowed")
    normalized = normalize_server_url(origin, "local")
    split = urlsplit(normalized)
    port = _split_port(split) or 80
    host = split.hostname or ""
    connect_host = _resolve_allowed_local_server(host, port)
    connection = http.client.HTTPConnection(connect_host, port, timeout=timeout_seconds)
    try:
        connection.request("GET", path, headers={"Accept": "application/json", "Host": _host_header(normalized)})
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise ProbeError("redirects are not allowed")
        if response.status < 200 or response.status >= 300:
            raise ProbeError(f"probe failed with HTTP {response.status}")
        if path == "/capabilities" and "application/json" not in (response.getheader("content-type") or "").lower():
            raise ProbeError("capabilities content-type must be application/json")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ProbeError("probe response exceeded max size")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ProbeError("probe response must be a JSON object")
        return payload
    except (OSError, json.JSONDecodeError) as exc:
        raise ProbeError(str(exc)) from exc
    finally:
        connection.close()
