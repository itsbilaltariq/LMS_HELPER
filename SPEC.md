# NUST LMS Lab Assistant - Specification

## 1. Overview & Purpose
NUST LMS Lab Assistant is a secure, developer-focused companion tool designed for students at the **National University of Sciences and Technology (NUST)**. It interacts with the university's Learning Management System (**https://lms.nust.edu.pk**) to retrieve lab assignments, parse tasks and rubrics, and assist students in developing, testing, understanding, and submitting their lab solutions through an ultra-fast LLM workflow powered by **Groq**.

---

## 2. Target Platform: NUST LMS
- **Portal URL**: `https://lms.nust.edu.pk`
- **Underlying Architecture**: Moodle (customized with `mb2nl` theme)
- **Authentication**: NUST Qalam Single Sign-On credentials
  - Standard endpoint: `https://lms.nust.edu.pk/login/index.php`
  - Form parameters: `username`, `password`, and CSRF protection `logintoken`
  - Mobile web service endpoint (if token enabled): `https://lms.nust.edu.pk/login/token.php?service=moodle_mobile_app`
- **Course & Assignment Modules**:
  - Course pages: `https://lms.nust.edu.pk/course/view.php?id={id}`
  - Assignment modules: `mod_assign` (`https://lms.nust.edu.pk/mod/assign/view.php?id={id}`)
  - Downloadable resources: `pluginfile.php` links for lab manual PDFs, starter code ZIPs, and test suites.

---

## 3. LLM Engine: Groq Cloud API
- **API Provider**: [Groq Cloud](https://console.groq.com)
- **Authentication**: `GROQ_API_KEY`
- **Target Models**:
  - Primary reasoning/code generation: `llama-3.3-70b-versatile` (or `llama-3.1-70b-versatile`)
  - Fast parsing & rubric extraction: `llama-3.1-8b-instant`
- **Key Advantage**: Sub-second time-to-first-token (TTFT) and high token throughput (hundreds of tokens/sec), enabling real-time interactive lab hints, fast test-failure iterations, and immediate code walkthrough generation.
- **Cost / Budget Controls**: Configurable per-job token limits and timeout controls.

---

## 4. System Architecture & Inputs / Outputs

```
+-----------------------------------------------------------+
|                      User Browser                         |
|      (Next.js Dashboard + Human Approval Review Gate)     |
+-----------------------------+-----------------------------+
                              | HTTPS / Cookie Sessions + CSRF
+-----------------------------v-----------------------------+
|                     FastAPI Core API                      |
|       - Argon2id Auth + Fernet Credential Encryption      |
|       - Job Management & Cryptographic Approval Gate       |
+--------------+-----------------------------+--------------+
               |                             |
+--------------v---------------+  +----------v--------------+
|   PostgreSQL / Redis Queue   |  |   Playwright Fetcher    |
| (Jobs, Audit Logs, Sessions) |  |   (NUST Moodle Worker)  |
+--------------+---------------+  +----------+--------------+
               |                             |
+--------------v---------------+             | Downloads Manuals & Starters
| Groq LLM Agent & Code Sandbox <-------------+
| - Task & Rubric Parser       |
| - TDD Solve & Hint Loop      |
| - Strict Isolated Sandbox    |
| - SHA-256 Bundle Producer    |
+------------------------------+
```

### Inputs
1. **Student Credentials**: Encrypted at rest using Fernet; decrypted only in-memory in isolated workers.
2. **NUST Course/Assignment Link**: Assignment URL or course selection from NUST LMS.
3. **Lab Assets**: PDF lab instructions, starter files, sample inputs/outputs.
4. **Execution Mode**: `Assist / Hint Mode`, `Step-by-step Walkthrough`, or `Verification & Solve`.

### Outputs
1. **Validated Code Artifacts**: Clean code meeting rubric guidelines.
2. **Pedagogical Walkthroughs**:
   - Explanation of design choices and algorithm trade-offs.
   - Viva / oral exam prep questions based on the student's solution.
3. **Test Results**: Output from dockerized local sandbox test runs.
4. **Verified Submission Archive**: Zip bundle bound to human approval digest (SHA-256) before upload to NUST LMS.

---

## 5. Non-Goals & Academic Policy Boundaries
- **No Unreviewed Auto-Submissions**: The system strictly enforces a human review gate. No artifact can be pushed to NUST LMS without the student inspecting the diff and clicking Approve with an active session and fresh CSRF token.
- **No Plagiarism / Blind Copying**: The assistant prioritizes conceptual understanding, detailed explanations, and hint-driven learning over black-box submission.
- **No Aggressive LMS Scraping**: Rate-limited requests with polite backoff to prevent any burden on NUST LMS infrastructure.
