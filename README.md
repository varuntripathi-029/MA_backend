# MX_rating — Backend

MX_rating scores how "agent-ready" a website is — how easily an AI agent (not a human with eyes and a mouse) can crawl it, understand its structure, and act on it. You give it a URL; it crawls the live page, runs a deterministic rule engine over the rendered DOM, scores six dimensions (trust, discoverability, structure, metadata, accessibility, structured data), and asks an LLM to write an evidence-linked narrative report on top of the rule engine's findings — never the other way around.

## How a scan works

1. **Crawl** (Playwright) — fetch one URL, capture rendered HTML, HTTP status, response headers, SSL info, robots.txt gating, and sitemap presence.
2. **Clean & extract** (BeautifulSoup/lxml) — parse the rendered DOM into structured features (headings, landmarks, JSON-LD, Open Graph, alt text, etc.).
3. **Rule engine** — ~13 pure, deterministic checks run over those features. No LLM involved, no HTML re-inspected.
4. **Machine profile** — check results and extracted features merged into one JSON object.
5. **Scoring** — a hand-weighted rubric (not regression-fit) turns the profile into a 0–1 score per dimension and an overall score. Weights live in one place (`app/pipeline/scoring.py`) and are also what `GET /api/methodology` serves, so the published methodology and the actual computed score can never drift apart.
6. **Recommendations** — deterministic, generated straight from failing checks.
7. **LLM reasoning** (Groq, Llama 3.3 70B) — the *only* LLM call in the pipeline. It narrates what the rule engine already found — purpose, target users, strengths/weaknesses, missing info — and never sets the score itself. Every claim it makes must cite a real path into the profile JSON; citations are re-validated after the call for both existence (does the path exist) and polarity (does the cited value actually support what the claim says), and any hallucination is logged rather than silently dropped or trusted.

Scans run as an in-process FastAPI `BackgroundTask` — `POST /api/scan` returns a scan id immediately with status `pending`, and `GET /api/report/{id}` is polled until the task moves it through `running → done/failed`. No queue, no worker process.

## Problems we hit along the way (and the fixes)

- **Windows + Playwright + async Postgres don't mix by default.** Playwright's async browser driver requires Windows' `ProactorEventLoop`; `psycopg`'s async mode hard-refuses to run under it. Fix: switched the DB driver to `asyncpg`, which has no such restriction, so crawler and DB session share one event loop in-process.
- **The Docker image's Playwright build silently drifted from the pinned pip version.** `pyproject.toml` only floors `playwright>=1.48`, so whatever pip actually resolved could be newer than the browser binaries baked into the base image, breaking the crawl at runtime with a version-mismatch error that only showed up in the container, not locally. Fix: re-run `playwright install --with-deps chromium` *after* `pip install` in the Dockerfile, and bumped the base image to match, so the on-disk browser build always matches whatever Playwright version is actually installed.
- **Migrations never ran in the deployed container**, and the API just crashed against an empty schema. Fix: added `docker-entrypoint.sh` to run `alembic upgrade head` before starting `uvicorn`, so every container boot self-migrates.
- **Free-tier Postgres (Neon) suspends its compute when idle**, and the first request after a cold start would hit a bare `OperationalError` and 500 out — whichever request happened to arrive first "woke" the database and paid for it with a failure. Fix: `pool_pre_ping` on the engine plus a `resilient_session()` wrapper that retries the initial `SELECT 1` a few times with backoff before handing the session to a request, so a sleeping DB just costs a couple seconds of latency instead of an error.
- **The LLM's structured-output mode wasn't actually enforced by the model we use.** Groq's strict `json_schema` response format isn't supported by the Llama models on Groq (only their `openai/gpt-oss-*` models) — confirmed against the live API, not assumed from docs. Fix: use the looser `json_object` mode (valid JSON guaranteed, not schema-enforced) and enforce the schema ourselves via Pydantic, raising rather than silently falling back to free-text parsing on a bad response.
- **LLMs cite things that don't back up their claim.** A citation path can resolve to a real field in the profile and still contradict the claim (e.g. an "agent weakness" citing a check that actually scored perfectly). Fix: every citation is polarity-checked against the value it points to, not just existence-checked, and mismatches are surfaced in the report instead of trusted at face value.

## Tech stack

- **FastAPI** + **Uvicorn** — async API layer
- **Playwright** (Python, Chromium) — headless rendering/crawling
- **BeautifulSoup4** + **lxml** — HTML parsing/cleaning
- **SQLAlchemy 2.0** (async) + **asyncpg** + **Alembic** — ORM, Postgres driver, migrations
- **Pydantic v2** / **pydantic-settings** — schemas and config
- **Groq** (Llama 3.3 70B) — the single LLM call for narrative reasoning
- **Postgres 16**, containerized via **Docker** / **docker-compose**
- **pytest** + **pytest-asyncio** — test suite (rules, scoring, recommendations, reasoning/citation validation, pipeline integration, API contract)

## Run it locally

1. Copy `.env.example` to `.env` and fill in `GROQ_API_KEY`.
2. `docker-compose up --build` (spins up Postgres + the backend, running migrations automatically on boot).
3. API is now live at `http://localhost:8000` (`GET /health` to check).
4. Hit `POST /api/scan` with a `url`, then poll `GET /api/report/{scan_id}` for results.

---

Varun Tripathi
