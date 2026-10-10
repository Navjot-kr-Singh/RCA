# Root Cause Analysis assistant

Describe a production issue in plain words and get likely root causes, recommended fixes, and the similar known issues the answer was based on.

## How it works

1. **Search.** The issue description is embedded and compared against a small knowledge base of known production issues, each with recorded causes and fixes.
2. **Ground.** If the closest known issue is similar enough (score of 0.75 or more), the three closest are passed to the model as context. The response is tagged `RAG` and includes those issues.
3. **Fall back.** Otherwise the model answers from general knowledge alone and the response is tagged `LLM_ONLY`.

## Project layout

| Path | What it is |
|---|---|
| `Backend/` | FastAPI service. `rca_engine.py` holds the retrieval and prompting logic (LangChain, OpenAI, FAISS). |
| `Backend/dataset/production_issues_75.json` | The knowledge base the backend searches. |
| `Frontend/` | React + Vite single-page app. |
| `dataset/` | A separate incident dataset and the scripts that built it. Not yet used by the backend. |

## Running it

You need Python 3.9+, Node 20+, and an OpenAI API key.

**Backend**

```bash
cd Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "OPENAI_API_KEY=your-key" > .env
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

The knowledge base is embedded on startup, so the first start makes one embeddings call.

**Frontend**

```bash
cd Frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The app expects the API at `http://127.0.0.1:8000`; to point it elsewhere, set `VITE_API_URL` in `Frontend/.env.local`.

## API

`POST /analyze` with `{"issue": "Redis out of memory errors"}` returns:

```json
{
  "mode": "RAG",
  "analysis": {
    "root_causes": ["..."],
    "solutions": ["..."],
    "confidence": 0.8,
    "explanation": "..."
  },
  "similar_issues": [{ "content": "...", "similarity_score": 0.81 }]
}
```

`similar_issues` is empty in `LLM_ONLY` mode. If the model's reply is not valid JSON, `analysis` is `{"error": "...", "raw_output": "..."}` instead. Interactive docs are at http://127.0.0.1:8000/docs.

## Datasets

- `gold_incidents.json`: 1,383 real production incidents, each with a source URL. See `DATASET_REPORT.md`.
- `synthetic_incidents.json`: 1,383 generated incidents in the same schema, marked `data_type: "synthetic"`. See `SYNTHETIC_REPORT.md`.

The raw scraped pages the gold set was extracted from are not included in this repository because of their size.
