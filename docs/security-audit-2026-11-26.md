# Security audit — authentication module (2026-11-26)

Source-only audit of `backend/modules/authentication` and its wiring, at commit `9a1d1ce`
(branch `fix/review-2026-11-24`). Four read-only scouts, three hunters, five independent
reviewers; no code executed, no traffic sent, no files changed by the audit.

Full records: `~/security-audits/imsi-team/run-1/` (`REPORT.md`, `findings.json`,
`coverage-ledger.json`). Every claim below carries its `file:line`.

## Findings

| # | Verdict | Severity | Finding | Evidence |
|---|---|---|---|---|
| F-01 | confirmed | high | The activity touch rewrites the whole session row, so a concurrent logout is undone and the session comes back as `ACTIVE` with its old refresh token id | `application/auth_service.py:243-244`, `infrastructure/persistence/repositories.py:59-74` |
| F-02 | confirmed | high | The refresh guard filters on `refresh_token_id`, which termination never changes, so a logout inside the refresh window is clobbered and new tokens are issued | `application/auth_service.py:200-227`, `repositories.py:60-72`, `domain/session.py:68-73` |
| F-03 | confirmed | medium | Existing accounts answer `ACCOUNT_LOCKED` after three failures while unknown ones keep answering `INVALID_CREDENTIALS`; the lockout is checked before the password, so three anonymous requests lock a known user for 15 minutes | `user_accounts/application/account_access_service.py:57-70`, `domain/exceptions.py:20-33` |
| F-04 | confirmed | medium | No authentication route has a per-IP rate limit; only `public_*` scopes exist | `config/settings/base.py:126-134`, `infrastructure/api/views.py:55-176` |
| N-01 | needs validation | — | `JWT_SIGNING_KEY` falls back to `sha256("jwt:" + SECRET_KEY)` with no warning; pre-auth tokens need no session row, so a known `SECRET_KEY` forges enrollment tokens | `config/settings/base.py:222-224` |
| N-02 | needs validation | — | The TOTP Fernet key is derived the same way, so a database dump plus the app secret decrypts every seed | `infrastructure/persistence/repositories.py:88-90` |
| N-03 | needs validation | — | Entrypoints default to `config.settings.dev`: `DEBUG=True` and `REFRESH_COOKIE_SECURE=False` when the environment does not say otherwise. No production settings module exists | `manage.py:9`, `config/wsgi.py:5`, `config/settings/dev.py:6,10` |
| R-01 | rejected | — | Plaintext `refresh_token_id` is not a bearer credential: the cookie is an HS256 JWT, so a database reader cannot use the id alone | `infrastructure/security/jwt_token_issuer.py:58-72` |

## Why F-01 and F-02 matter

Both are the same defect: `SessionRepository.update()` writes `status`, `termination_reason`,
`terminated_at` and `refresh_token_id` unconditionally, and no write path filters on the
current status. Under the configured READ COMMITTED (`config/settings/base.py:87-89`) the
late `UPDATE` still matches the row, so the last writer wins and the server's only revocation
record is advisory. Fix shape: write activity alone (`last_activity_at` guarded by
`status='ACTIVE'`), and add `status='ACTIVE'` to the conditional update used by refresh.

## Hardening notes (not findings)

`NUM_PROXIES` is configured but never read, so audited `source_ip` is the proxy address;
bcrypt truncates at 72 bytes while login accepts 128 characters; `/api/docs/` is public in
every environment; `confirm_enrollment` does not consult the account lock the way
`verify_code` does.

## What was not done

No runtime reproduction: F-01/F-02 need a concurrent run, F-03/F-04 are visible in source.
Tier `core` only: web-protocol, AI/LLM, supply-chain and cloud companions were out of scope,
and the audit covers the six ledger units, not the whole backend.
