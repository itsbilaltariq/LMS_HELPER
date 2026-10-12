# NUST LMS Lab Agent: Project TODO

**Target LMS:** National University of Sciences and Technology (NUST) LMS ([lms.nust.edu.pk](https://lms.nust.edu.pk)) (Moodle platform)  
**LLM Engine:** Groq Cloud API (`GROQ_API_KEY`, Llama 3.3 70B / 3.1 8B)  
**GitHub Account:** `itsbilaltariq` (`mtariq.bscs24seecs@seecs.edu.pk`)

Legend: `[x]` done, `[ ]` pending. Phases are ordered; each has a **Done when** line.

---

## Phase 0: Ground rules (do first)
- [x] Decide scope: assistant that helps you do the lab (explain, hint, check, viva prep) with mandatory human approval before submission
- [x] Check LMS terms of service and architecture on automated login and scraping (Moodle platform with Qalam SSO credentials and CSRF `logintoken`)
- [x] Write a one-page spec: inputs, outputs, non-goals (`SPEC.md`)
- [x] Create repo, `.gitignore` (`.env`, `*.pem`, `downloads/`, `__pycache__/`)
- [x] Add pre-commit hooks: `ruff`, `black`, `mypy`, `gitleaks` (secret scan)

**Done when:** spec written and policy question answered.

---

## Phase 1: Project setup
- [x] Python 3.12 venv, `pyproject.toml`, pinned deps (`pip-compile` or `uv`)
- [x] Folder layout: `app/`, `workers/`, `agent/`, `sandbox/`, `tests/`, `infra/`
- [x] `.env.example` (no real values): `APP_SECRET`, `FERNET_KEY`, `DATABASE_URL`, `REDIS_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `LMS_BASE_URL`
- [x] Config loader with fail-fast validation (`pydantic-settings`)
- [x] Structured logging (JSON), with a redaction filter for secrets and passwords
- [x] Makefile / task runner / PowerShell scripts: `dev`, `test`, `lint`

**Done when:** `dev` starts an empty app and CI-style `lint` and `test` pass.

---

## Phase 2: Secure API core (starter: `app.py`)
- [x] Cookie sessions: `HttpOnly`, `Secure`, `SameSite=Strict`, `__Host-` prefix
- [x] CSRF token bound to session (HMAC)
- [x] Argon2id password hashing, dummy-hash timing safety
- [x] Login rate limiting
- [x] Security headers middleware
- [x] Fernet-encrypted LMS credentials
- [x] Approval gate bound to artifact SHA-256
- [x] Split `app.py` into modules: `auth.py`, `jobs.py`, `security.py`, `models.py`
- [ ] Replace in-memory `DB` with PostgreSQL (SQLAlchemy 2 + Alembic migrations)
- [ ] Move rate limiting to Redis (works across multiple workers)
- [ ] Session rotation on login; revoke all sessions on password change
- [ ] Idle timeout plus absolute timeout
- [ ] Persist audit log to DB (append-only table)
- [ ] User creation CLI (`python -m app.create_user`), no open registration
- [ ] Optional: TOTP 2FA
- [ ] Unit tests: login, wrong password, CSRF missing/bad, expired session, IDOR (other user's job), approve-then-modify-then-submit rejected

**Done when:** all auth and gate tests pass against Postgres.

---

## Phase 3: Frontend (Next.js)
- [ ] Next.js app served behind the same origin as the API (Caddy path routing: `/api` to FastAPI)
- [ ] Login page; no tokens in JS, no localStorage/sessionStorage
- [ ] `fetch` with `credentials: "include"`; read `__Host-csrf` cookie and send as `X-CSRF-Token`
- [ ] Pages: Dashboard, New Lab, Job detail (progress), Review (diff + summary), Settings (NUST LMS creds)
- [ ] Review page: side-by-side diff, rubric checklist, "Approve" button (disabled until you scroll/view the full artifact)
- [ ] Strict CSP via Next middleware (nonce-based, no `unsafe-inline`)
- [ ] Escape all rendered LLM output (treat as untrusted); no `dangerouslySetInnerHTML`
- [ ] Error and loading states, session-expired redirect

**Done when:** you can log in, create a job, and approve one from the UI.

---

## Phase 4: Fetch worker (Playwright - NUST Moodle)
- [ ] Separate container/process, no direct access to user DB; talks via the queue
- [ ] Log into NUST LMS (`https://lms.nust.edu.pk/login/index.php`) with decrypted creds, handling Moodle `logintoken`
- [ ] Prefer official Moodle mobile web service token (`/login/token.php?service=moodle_mobile_app`) if enabled for user
- [ ] Download lab PDF and starter files to a per-job temp dir
- [ ] Validate downloads: size cap, MIME check, filename sanitization (no path traversal)
- [ ] Polite rate limiting, retries with backoff, hard timeouts
- [ ] Never log page content that includes credentials; screenshots off in prod
- [ ] Tests with a mocked NUST LMS (local static Moodle pages)

**Done when:** worker fetches a lab from NUST LMS into a clean job folder.

---

## Phase 5: Parse stage
- [x] Extract text and structure from PDF (PyMuPDF); OCR fallback for scanned PDFs
- [x] Groq LLM step to produce structured JSON: tasks, deliverables, rubric, deadlines, allowed languages/tools
- [x] Validate JSON against a pydantic schema; retry on invalid output
- [x] Treat document text as untrusted (prompt-injection defense): never let lab text trigger tool calls or change system rules
- [x] Store parsed result with a version number

**Done when:** a sample lab PDF becomes a validated task list.

---

## Phase 6: Agent worker (Groq LLM core)
- [x] Groq API client with timeouts, retries, and a per-job token budget (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`)
- [ ] Tool-use loop with a strict tool allowlist: `write_file`, `run_tests`, `read_file`
- [ ] Planner prompt: map each rubric item to a step
- [ ] Solve loop: write, run, read errors, fix, with a max-iteration cap
- [ ] Self-critique pass against the rubric
- [x] **Explain mode:** for every solution, produce a walkthrough (why this approach, how each part works, likely viva questions)
- [x] **Hint mode:** give hints instead of the full solution
- [ ] Prompt-injection tests (malicious text in lab files)
- [ ] Record all prompts and outputs per job (without secrets) for debugging

**Done when:** given a parsed lab, the Groq agent produces code plus an explanation that passes the lab's own checks.

---

## Phase 7: Sandbox
- [ ] Docker image: non-root user, read-only root FS, `--network none`
- [ ] Limits: CPU, memory, PIDs, wall-clock timeout, output size cap
- [ ] Drop all capabilities, `no-new-privileges`, seccomp default profile
- [ ] Mount only the job directory; nothing from the host or secrets
- [ ] Per-language runners as needed (Python, Java, C++, SystemVerilog/Vivado is likely **not** sandboxable; handle manually)
- [ ] Tests: fork bomb, infinite loop, big output, network attempt, file escape; all contained

**Done when:** hostile code can't escape, hang, or exhaust the host.

---

## Phase 8: Review gate and submit
- [ ] Artifact bundle builder (zip plus manifest with file hashes)
- [ ] Review summary: what changed, test results, rubric coverage, warnings
- [ ] Approve endpoint binds to bundle digest (SHA-256); require fresh CSRF and a recent session
- [ ] Optional: re-enter password to approve (step-up auth)
- [ ] Upload worker (Playwright): verifies the digest before uploading to NUST LMS; refuses on mismatch
- [ ] Post-upload verification: confirm NUST LMS shows the submission; save receipt
- [ ] Dry-run mode (fills the submission form but doesn't click submit) for testing
- [ ] Deadline guard: warn if near or past the deadline

**Done when:** an approved job uploads exactly the approved bundle, and a tampered one is refused.

---

## Phase 9: Infra and hardening
- [ ] `docker-compose`: caddy, api, web, postgres, redis, workers
- [ ] Caddy: automatic HTTPS, HSTS, HTTP to HTTPS redirect
- [ ] Secrets via Docker secrets or a secret manager, not in the image
- [ ] Postgres: least-privilege DB user, backups, encrypted volume
- [ ] Dependency audit: `pip-audit`, `npm audit`, Dependabot
- [ ] Static analysis: `bandit`, `semgrep`
- [ ] OWASP ASVS L2 checklist pass
- [ ] Threat model doc (STRIDE) for each component
- [ ] Incident basics: key rotation procedure, "revoke all sessions" command

**Done when:** `docker compose up` gives a hardened stack and audits are clean.

---

## Phase 10: Testing and QA
- [ ] Unit tests (target >80% on auth, gate, parsers)
- [ ] Integration tests with mocked NUST LMS and a fake LLM
- [ ] E2E (Playwright): login, create job, review, approve
- [ ] Security tests: CSRF, IDOR, session fixation, rate-limit bypass, XSS via LLM output
- [ ] Load sanity test on login and job creation
- [ ] CI pipeline: lint, type-check, tests, audits on every push

---

## Phase 11: Docs and ops
- [ ] README: setup, env vars, architecture diagram
- [ ] `SECURITY.md`: threat model, how to report issues
- [ ] Runbook: deploy, rotate secrets, restore backup
- [ ] Changelog and version tags
