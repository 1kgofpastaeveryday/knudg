import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts import knudg_post_private_card


class HtmlErrorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        body = b"<html><body>Web App - Unavailable</body></html>"
        self.send_response(403)
        self.send_header("content-type", "text/html")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_post_json_reports_non_json_http_error_without_crashing():
    server = serve(HtmlErrorHandler)
    try:
        status, payload = knudg_post_private_card.post_json(
            f"http://127.0.0.1:{server.server_port}",
            "test-token",
            {"workspace": "closed-launch-manual", "card": {"title": "test"}},
            "sha256:" + "a" * 64,
        )
    finally:
        server.shutdown()

    assert status == 403
    assert payload["status"] == "http_error"
    assert payload["error_class"] == "non_json_response"
    assert "text/html" in payload["detail"]
    assert "Web App - Unavailable" in payload["body_preview"]


def test_effective_api_url_rejects_stale_azure_endpoint():
    with pytest.raises(SystemExit) as exc:
        knudg_post_private_card.effective_api_url(knudg_post_private_card.STALE_AZURE_API_URL)

    assert "old Azure App Service endpoint is no longer valid" in str(exc.value)


def test_parse_json_response_rejects_non_object_json():
    payload = knudg_post_private_card.parse_json_response(200, "application/json", json.dumps(["bad"]).encode())

    assert payload["status"] == "http_error"
    assert payload["error_class"] == "non_object_json_response"
