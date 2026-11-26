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

## Status after `64972f6` (26-nov, team push)

`64972f6` (merged on top of `7ae5c76`, which brings this branch into `first-release`) closed
two items and left the rest open. State of each record on that commit:

| # | State on `64972f6` | What changed |
|---|---|---|
| F-01 | **Open** | `authenticate()` still calls `self._sessions.update(session)` with no status predicate (`application/auth_service.py:255-256`) and `update()` still writes every lifecycle column (`infrastructure/persistence/repositories.py:59-74`) |
| F-02 | **Open** | The failure type changed to `RefreshConflict` so the shared cookie survives, but the guard is still `WHERE pk [AND refresh_token_id]`; termination does not change that column, so the revival race is unchanged |
| F-03 | **Open** | `ACCOUNT_LOCKED` is still a distinct code (`domain/exceptions.py:21`); no per-IP limit was added |
| F-04 | **Open** | No `throttle_scope` on any auth view; `config/settings/` still has no production module |
| N-01/N-02 | **Open** | `JWT_SIGNING_KEY` and `TOTP_ENCRYPTION_KEY` keep the silent derivation (`config/settings/base.py:222-224,233`) |
| N-03 | **Open** | Entrypoints still default to `config.settings.dev` |
| Hardening: enrollment lock | **Fixed** | `start_enrollment` and `confirm_enrollment` now refuse a locked account (FR-01-14) |
| Hardening: audit log | **Improved beyond the note** | Migration `0004` also rejects `TRUNCATE`, which row triggers never fire on |

The refresh-cookie race this push fixes is a different one from F-02: it is about two tabs
erasing a shared cookie, not about a termination being overwritten.

## Status after the fixes of F-01…F-04 (26-nov, Cristofer Ordoñez)

F-01, F-02 and F-03a were first **reproduced** with tests (two copies of the same session row
written in the problematic order; four failed logins against a real and an unknown email), then
fixed. Each fix has a regression test in `backend/tests/authentication/test_api.py`.

| # | State | Fix |
|---|---|---|
| F-01 | **Fixed** | `SessionRepository.update()` was replaced by three intent methods. `record_activity` writes only `last_activity_at`, and only `WHERE status = 'ACTIVE'`; if it matches nothing, the request fails with the session's closing reason |
| F-02 | **Fixed** | `rotate_refresh_token` writes only `refresh_token_id`, `WHERE status = 'ACTIVE' AND refresh_token_id = <expected>`. A session closed meanwhile answers its closing reason (cookie cleared); a lost race between tabs still answers `REFRESH_CONFLICT` (cookie kept) |
| F-01/F-02 (related) | **Fixed** | `record_termination` is also guarded by `status = 'ACTIVE'`: the first closing reason wins and a second closing writes nothing and is not audited twice. Activity writes can no longer undo a concurrent rotation either |
| F-03a (enumeration) | **Fixed** | Unknown emails follow the same counter and lock as real accounts (`UnknownEmailAttempts`, stored in the cache under an HMAC of the email), so both get the same answers at the same attempts and with the same timing |
| F-03b (lockout DoS) | **Accepted** | Inherent to FR-01-01/FR-01-14 (the lock is checked before the password). Mitigated by F-04 and the manual unlock (US 1.23); recorded in the corrections README |
| F-04 | **Fixed** | Per-IP `throttle_scope` on every auth view: `auth_login` 10/min, `auth_code` 20/min, `auth_refresh` 60/min. 429 answers `code: RATE_LIMITED` with a Spanish message |
| Hardening: `NUM_PROXIES` | **Fixed** | Partly accurate: DRF's throttles did read it, but `client_ip()` (the audited `source_ip`) used `REMOTE_ADDR`. It now uses the same `get_ident` as the throttles and drops values that are not IP addresses |
| N-01…N-03, bcrypt 72 bytes, public `/api/docs/` | **Open (deployment)** | Planned as a production settings module; see CLAUDE.md pending items and item 7 of the corrections README |

## Hardening notes (not findings)

`NUM_PROXIES` is configured but never read, so audited `source_ip` is the proxy address;
bcrypt truncates at 72 bytes while login accepts 128 characters; `/api/docs/` is public in
every environment.

## What was not done

No runtime reproduction: F-01/F-02 need a concurrent run, F-03/F-04 are visible in source.
Tier `core` only: web-protocol, AI/LLM, supply-chain and cloud companions were out of scope,
and the audit covers the six ledger units, not the whole backend.
