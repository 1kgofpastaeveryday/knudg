# Auth Verifier Gate

Status: draft scaffold, non-local auth closed

`fixtures/auth-verifier-gate.draft.json` is the PR-004 scaffold for replacing
local-development HS256 request contexts before protected private/team,
staging, production, public, or enterprise paths.

Validate it:

```powershell
npm run auth:gates
```

The draft gate keeps HS256 limited to `local`, with production, team, and
staging disabled. It records the required negative tests for `alg=none`, wrong
audience, wrong issuer, stale keys, stale nonces, proof/key mismatch,
cross-resource replay, and unchanged RLS call sites.

This scaffold does not select a non-local verifier profile. Acceptance requires
an asymmetric JWKS or KMS/Vault-style profile, sender-constrained proof,
nonce/replay storage, key rotation tests, environment assertions, and backend
swap tests.
