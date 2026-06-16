# Public Repository Operations

Knudg is already public, so the repository posture is maintained through a
mix of committed checks and GitHub repository settings.

## Committed Checks

Run these before merging public-facing changes:

```powershell
npm run public:release-check
npm run secret:scan -- --history
npm test
npm run check:lp
```

`npm run secret:scan` is a high-confidence local scanner for known token and
private-key shapes. It complements GitHub native secret scanning; it does not
replace rotating any exposed real secret.

## GitHub Settings To Keep Enabled

These settings are controlled in GitHub, not by repository files:

- Secret scanning alerts for the public repository.
- Push protection when available for the account or organization.
- Dependabot alerts and security updates.
- Private vulnerability reporting.
- Branch protection for `main`, requiring CI before merge.

## Issue Routing

Public issues must use the templates under `.github/ISSUE_TEMPLATE/`.
Vulnerabilities and accidental private-data exposure reports must go through
the private security reporting path instead of public issues.
