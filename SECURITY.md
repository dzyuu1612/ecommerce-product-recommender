# Security policy

## The most important thing on this page

**recsys-lite has no authentication, no authorisation, and no rate limiting.**

Every endpoint is reachable by anyone who can reach the port. Anyone can read
the catalog, read the full event log, and **write events for any shopper id**.
This is a deliberate scope decision for a demonstration project, not a bug —
but it means:

> **Do not expose this on the public internet.** Run it on localhost, on a
> private network, or behind a proxy that terminates TLS and authenticates
> requests. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#behind-a-reverse-proxy).

---

## Supported versions

This is a demonstration project without a release cadence. Security fixes land
on `main`; there are no backported branches.

| Version | Supported |
|---|---|
| `main` | Yes |
| Tagged releases | Best effort |

---

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Email **baoduynguyen1612@gmail.com** with:

- What the issue is and where in the code it lives
- Steps to reproduce, ideally a minimal case
- What an attacker could achieve
- Any suggested fix

You can expect an acknowledgement within **7 days** and an assessment within
**30 days**. If you would like credit in the fix commit, say so; if you would
rather stay anonymous, that is respected.

Please give a reasonable window to ship a fix before disclosing publicly.

---

## What is in scope

Bugs where the code does something worse than its documented design:

- Injection through a request that reaches SQL or the filesystem
- Path traversal via the static-file mount
- A crash or hang triggered by a well-formed request
- Anything in a dependency that this project's usage makes exploitable
- Cross-site scripting in the console — the frontend escapes interpolated
  values with `esc()`; a bypass is a real finding

## What is out of scope

Known, documented consequences of the project's scope. Reporting these is not
a vulnerability report:

| Not a vulnerability | Why |
|---|---|
| No authentication on any endpoint | Documented above and in the README |
| Anyone can POST events for any `user_id` | The demo has no identity model |
| The shopper switcher lets you "become" anyone | It is a demo affordance, not a login |
| `/metrics` is unauthenticated | Restrict it at the proxy |
| SQLite allows one writer | Storage choice, documented in ARCHITECTURE.md |
| No CSRF tokens | There are no sessions and no privileged state to forge |
| No password policy | There are no accounts |

If you think one of these is worse than documented — for example a way to
corrupt the database rather than merely write to it — that **is** in scope.

---

## Design notes relevant to security

**SQL.** Every query uses parameter binding. The one place a query is built
dynamically is the `IN (...)` clause in `/api/recommend`, where only the
**number** of `?` placeholders is interpolated; the values are always bound.

**Input validation.** Request bodies are Pydantic models. `event_type` is
constrained by regex, batch size is capped at 100, and `limit` parameters are
clamped server-side rather than trusted.

**Batch atomicity.** `/api/events/batch` validates every item id before writing
any row, so a partially-valid order writes nothing. Covered by test.

**Output escaping.** The console escapes every interpolated value before
inserting it into the DOM. Product titles are generated, but the escaping does
not depend on that.

**Container.** The Docker image runs as `uid=1000(appuser)`, not root.

**Secrets.** There are none — no API keys, tokens, or credentials anywhere in
the codebase or its configuration. Nothing is read from a `.env`. If you add
an integration that needs a secret, do not commit it; the repository has no
secret-management story and `.gitignore` should not be your only defence.

**Dependencies.** Five runtime dependencies (`fastapi`, `uvicorn`, `pydantic`,
`torch`, `numpy`). Keep them current; `pip list --outdated` is enough at this
size.

---

## Hardening checklist before any shared deployment

- [ ] Bind to `127.0.0.1` and put an authenticating reverse proxy in front
- [ ] Terminate TLS at the proxy
- [ ] Rate-limit `POST /api/events` and `POST /api/events/batch`
- [ ] Restrict `/metrics` to your monitoring network
- [ ] Run the container as a non-root user (the image already does)
- [ ] Put the SQLite file on a volume only the app user can read
- [ ] Back it up — it is the entire system of record
- [ ] Decide who is allowed to write events, and enforce it above the app
