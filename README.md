# NUST LMS Helper (`LMS_HELPER`)

> An intelligent, pedagogical lab companion and automation system built specifically for the **National University of Sciences and Technology (NUST)** LMS portal ([lms.nust.edu.pk](https://lms.nust.edu.pk)), powered by **Groq Cloud API**.

---

## 🎯 Target Platform & LLM Engine
- **Target LMS:** [https://lms.nust.edu.pk](https://lms.nust.edu.pk) (Moodle platform with NUST Qalam Single Sign-On).
- **LLM Engine:** [Groq Cloud](https://console.groq.com) (`GROQ_API_KEY`), utilizing ultra-high-throughput models:
  - `llama-3.3-70b-versatile` (Code generation, reasoning, viva question generation)
  - `llama-3.1-8b-instant` (Fast rubric parsing, extraction, and hint generation)

---

## 🔒 Security & Academic Integrity Architecture
1. **Cryptographic Human Approval Gate:** No code or submission can ever be submitted to NUST LMS without the student inspecting the diff and clicking Approve. The approval endpoint is cryptographically bound to the SHA-256 digest of the artifact bundle.
2. **Encrypted LMS Credentials:** NUST Qalam credentials are encrypted at rest with Fernet (`cryptography`) and only decrypted in-memory inside isolated worker tasks.
3. **Session & CSRF Protection:** Cookie sessions (`HttpOnly`, `SameSite=Strict`, `__Host-` prefix) coupled with HMAC-SHA256 CSRF validation bound to the active session.
4. **Argon2id Password Hashing:** Includes timing-attack mitigations (dummy verify for non-existent users).
5. **ASVS Security Headers:** Strict CSP, HSTS, X-Content-Type-Options (`nosniff`), X-Frame-Options (`DENY`).
6. **Secret Redaction in Logs:** JSON structured logging automatically redacts Groq API keys (`gsk_...`), tokens, and passwords.

---

## 📁 Repository Structure
```
LMS_helper/
├── app/                  # FastAPI Application Core
│   ├── auth.py           # Authentication, session lifecycle, rate limiting
│   ├── config.py         # Fail-fast settings (pydantic-settings)
│   ├── jobs.py           # Lab jobs & SHA-256 Approval Gate
│   ├── logging.py        # Structured JSON logs with secret redaction
│   ├── main.py           # Application entrypoint & middleware
│   ├── models.py         # Pydantic data schemas
│   └── security.py       # Argon2id, Fernet, CSRF HMAC, digests
├── agent/                # Groq LLM Assistant Core
│   └── groq_client.py    # Groq client with budget limits, Viva & Hint modes
├── workers/              # Playwright fetcher & submitter workers
├── sandbox/              # Isolated execution sandbox
├── tests/                # Automated test suite (Ruff + Pytest)
├── infra/                # Docker & Caddy infrastructure definitions
├── SPEC.md               # Detailed system specification
├── TODO.md               # Phased roadmap & milestone checklist
├── pyproject.toml        # Pinned dependencies & lint configuration
└── run.ps1               # PowerShell dev/test/lint task runner
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+
- Git

### 2. Environment Configuration
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```
Key variables to supply:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
APP_SECRET=your-random-32-byte-secret
FERNET_KEY=your-generated-fernet-key
LMS_BASE_URL=https://lms.nust.edu.pk
```

### 3. Run with PowerShell Runner
```powershell
# Run test suite
.\run.ps1 test

# Run linter and formatting checks
.\run.ps1 lint

# Start FastAPI dev server (http://localhost:8000)
.\run.ps1 dev
```
