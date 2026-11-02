# OnCall Room

**Your on-call team, with the memory of 2,856 past outages.**

OnCall Room turns a Discord channel into an incident war room. When an alert arrives, three AI agents work alongside the on-call engineers in a Switch room. One triages the alert, one finds likely root causes in 2,856 real production incidents, and one checks the system and proposes a fix. No fix is applied until a person approves it.

Built for the Flip the Switch hackathon (WeMakeDevs × Switch).

## The problem

- An alert fires at 3 AM, and the on-call engineer is alone with the logs and a search engine.
- Another company has often hit the same failure and published how they fixed it, but that knowledge doesn't reach the engineer in time.
- After the incident nobody writes the postmortem, so the next on-call starts from zero.

## How it works

See the [architecture diagram](docs/architecture.md).

1. **Alert.** `scripts/alert.sh` runs a synthetic checkout against the service. If it fails, the alert is posted in the incident channel.
2. **Triage.** The Triager restates the alert in one line, sets severity and category, and hands it to the RCA Agent.
3. **Root cause.** The RCA Agent asks the RCA API, which searches 2,856 past incidents, and posts the top hypotheses with evidence IDs and source links.
4. **Checks.** The Fixer runs read-only checks, pastes the exact output, and proposes one fix as an exact command.
5. **Approval.** A person replies `@<team>-fixer approve`. Only then does the Fixer apply the fix, which verifies itself.
6. **Learning loop.** The Triager writes the postmortem and posts the resolved incident to `POST /incidents`. It joins the index as `LOCAL-0001`, and the next similar alert cites it.

## Why Switch is central

Switch is where the agents and the people meet. Each agent acts only on messages that address it by name, so every handoff (Triager to RCA to Fixer) is an @mention in the shared room that the whole team can read. The approval is a person's message in that same room, and the room keeps the history for whoever joins the incident later. Without Switch the agents could neither hand work to each other nor ask the team for a decision.

## Quickstart

You need Python 3.9+. No OpenAI key is needed in demo mode.

1. **Set up** once, from the repository root:

   ```bash
   scripts/setup.sh
   ```

2. **Start the RCA API** on port 8000. `RCA_DEMO_MODE=1` answers from cached live answers for the three demo scenarios; leave it out and put `OPENAI_API_KEY` in `Backend/.env` for live answers to any issue.

   ```bash
   cd Backend && RCA_DEMO_MODE=1 .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
   ```

3. **Start the demo shop** on port 8001, in a second terminal:

   ```bash
   cd demo-shop && ../Backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
   ```

4. **Run the scenario** from the repository root, in a third terminal:

   ```bash
   scripts/break.sh redis-oom   # checkout starts returning 503
   scripts/alert.sh             # prints the alert; posts it to Discord if ALERT_WEBHOOK_URL is set
   scripts/fix.sh redis-oom     # restores the cache, then checks checkout and health
   ```

   With `ALERT_MENTION` set to the triager's mention (for example `ALERT_MENTION='<@&1234>'`), the posted alert addresses the triager. To find the mention, send `\@vertos-triager` in Discord and copy what appears.

5. **Agents.** In Switch Console, open **Templates**, paste [switch/oncall-room.template.yaml](switch/oncall-room.template.yaml), set **OnCall Room repo folder** to this repository's absolute path, and create. It adds the Triager, RCA Agent and Fixer to the `incidents` room, or creates a new room if there is none. Their instructions are also in [switch/agent-instructions.md](switch/agent-instructions.md).

Tests: `cd Backend && .venv/bin/python -m unittest tests.test_oncall tests.test_rag` and `cd demo-shop && ../Backend/.venv/bin/python -m unittest tests.test_shop`.

## Demo scenarios

| Scenario | Break | Fix | Status |
|---|---|---|---|
| Redis out of memory: checkout returns 503 | `scripts/break.sh redis-oom` | `scripts/fix.sh redis-oom` | Ready |
| Database connection pool exhausted | | | Planned |
| Bad deploy or config typo | | | Planned |

In the Redis scenario, `break.sh` shrinks the shop's in-memory cache and sets the `noeviction` policy, so new checkouts fail with Redis's real OOM error. `fix.sh` switches the policy to `allkeys-lru` and restores the limit, without deleting the orders already in the cache.

## Safety

- **Human approval.** The Fixer applies a fix only after a person addresses it with "approve". Approval from another agent, or a vague "looks good", doesn't count. See [switch/agent-instructions.md](switch/agent-instructions.md).
- **Read-only first.** The Fixer's only check is `GET /health`, which changes nothing.
- **Sandbox only.** The demo shop listens on 127.0.0.1, and every script refuses to run unless `SHOP_URL` points at localhost. The shop's `/admin/cache/config` endpoint has no authentication; it exists only for the local sandbox and must never be exposed.
- **Evidence.** The RCA API drops citations to incidents it did not retrieve, and the RCA Agent may cite only IDs from the API response.
- **Secrets.** The OpenAI key lives in `Backend/.env`, which is gitignored, and the Discord webhook URL is read from the `ALERT_WEBHOOK_URL` environment variable. Neither is committed. Demo mode needs no key at all.

## Technologies

- **Agents and chat:** Switch, Discord
- **RCA API:** Python, FastAPI, OpenAI (`gpt-4.1-mini`, `text-embedding-3-small`), FAISS, BM25
- **Demo shop:** FastAPI, Uvicorn, Pydantic, unittest
- **Scripts:** Bash, curl
- **Apps:** React + Vite (analysis app), Next.js (landing site)

## Team

Vertos: Navjot Kumar Singh (lead) and Sneha Mishra.

## RCA engine

Describe a production issue in plain words and get likely root causes, recommended fixes, and the similar known issues the answer was based on.

### How the engine works

1. **Search.** The description is rewritten into a clean symptom, then matched against 2,856 past production incidents using both embeddings and keyword search. A model reranks the candidates and the top five are kept, at most two per organisation.
2. **Ground.** If the best match is relevant enough (4 out of 10 or more), those incidents are passed to the model as evidence. The response is tagged `RAG` and each hypothesis cites the incidents that support it.
3. **Fall back.** Otherwise the model reasons without past incidents and the response is tagged `LLM_ONLY`.

### Project layout

| Path | What it is |
|---|---|
| `Backend/` | FastAPI service. `main.py` is the API; `rag/` holds retrieval, reranking and analysis. |
| `Backend/index/` | The prebuilt search index. Rebuild it with `python -m rag.build_index`. |
| `Backend/data/` | The cleaned incident set, embeddings and evaluation results. |
| `Backend/tests/` | Offline unit tests: `python -m unittest tests.test_rag`. |
| `Frontend/` | React + Vite analysis app. |
| `Landing/` | Public site (Next.js, Clerk sign-in): landing page, dashboard, privacy and terms. See its own README. |
| `dataset/` | The incident datasets and the scripts that built them. |
| `demo-shop/` | Sandbox checkout service with a fake Redis, used for the incident demo. |
| `scripts/` | `break.sh`, `fix.sh` and `alert.sh` for the demo scenarios. |
| `switch/` | Switch template and agent instructions for the incident room. |
| `docs/` | Architecture diagram. |
| `LICENSE` | MIT, for the code. |

`Backend/rca_engine.py` and `Backend/dataset/production_issues_75.json` are the earlier, smaller engine. The API no longer uses them.

### Running it

You need Python 3.9+, Node 20+, and an OpenAI API key.

**Backend**

```bash
cd Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "OPENAI_API_KEY=your-key" > .env
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

The search index ships with the repository, so startup makes no API calls. By default the model is `gpt-4.1-mini`; set `RCA_LLM_MODEL`, or `RCA_LLM_BASE_URL` for a local OpenAI-compatible server, in `Backend/.env` to change that. Embeddings always use OpenAI.

**Frontend**

```bash
cd Frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The app expects the API at `http://127.0.0.1:8000`; to point it elsewhere, set `VITE_API_URL` in `Frontend/.env.local`.

### API

`POST /analyze` with `{"issue": "Redis out of memory errors"}` returns, among other fields:

```json
{
  "mode": "RAG",
  "analysis": {
    "summary": "...",
    "category": "database_issue",
    "severity": "High",
    "hypotheses": [{ "cause": "...", "likelihood": 0.6, "evidence_ids": ["GOLD-0621"], "reasoning": "..." }],
    "first_checks": ["..."],
    "fix_steps": ["..."],
    "root_causes": ["..."],
    "solutions": ["..."],
    "confidence": 0.6,
    "explanation": "..."
  },
  "similar_incidents": [{ "id": "GOLD-0621", "org": "...", "issue": "...", "root_cause": "...", "solution": "...", "source_url": "..." }],
  "similar_issues": [{ "content": "...", "similarity_score": 1.0 }]
}
```

`root_causes`, `solutions`, `confidence`, `explanation` and `similar_issues` are the simpler fields the analysis app reads. `summary_markdown` is the same answer as short Markdown for a chat message; the RCA Agent posts it as is. A live answer takes roughly 6 to 9 seconds. `GET /` reports how many incidents are indexed and whether demo mode is on. Interactive docs are at http://127.0.0.1:8000/docs.

`POST /incidents` adds a resolved incident to the index (the learning loop):

```json
{ "issue": "...", "root_cause": "...", "solution": "...", "category": "database_issue", "severity": "Critical" }
```

It returns `{"id": "LOCAL-0001", "embedded": true, "incidents_indexed": 2857}`. Incidents are kept in `Backend/data/learned_incidents.json` (gitignored) and re-indexed on every start. In demo mode they are found by keyword search only, and shown first among the similar incidents.

**Demo mode.** With `RCA_DEMO_MODE=1`, `/analyze` answers from `Backend/demo/cache.json`, one live answer per demo scenario, picked by the words the issue shares with each. An issue that matches none gets a 404 listing the cached ones. Rebuild the cache with `cd Backend && .venv/bin/python -m rag.demo_cache` (needs a key).

### Datasets

- `gold_incidents.json`: 2,856 real production incidents, each with a source URL. See `DATASET_REPORT.md`.
- `synthetic_incidents.json`: 1,383 generated incidents in the same schema, marked `data_type: "synthetic"`. See `SYNTHETIC_REPORT.md`.

The raw scraped pages the gold set was extracted from are not included in this repository because of their size.

### Data sources and attribution

Every incident in `gold_incidents.json` was extracted from a public incident report: company status-page postmortems (2,504), GitHub availability reports (73), engineering-blog postmortems (55), the danluu/post-mortems index (25) and an AWS post-event summary (1), plus 198 hand-curated entries. They cover 849 organisations. Each entry keeps the `source_url` of the report it came from, and the original reports belong to the organisations that published them.
