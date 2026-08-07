# GeminiRAG — Multimodal Enterprise RAG

ChatGPT-style multimodal RAG over **text, PDF, images, audio, and video**, using **Gemini Embedding 2 Preview**, **Gemini** for generation, **Pinecone** for vectors, **FastAPI** for the API, and **Next.js (App Router) + TypeScript + Tailwind** for the UI.

---

## What it does

1. **Upload** files (separate from chat) → validate → extract/describe → embed → store file → upsert to Pinecone  
2. **Send** a question → embed query → retrieve similar chunks → generate an answer with citations (and image previews when available)

Supported modalities (aligned with Gemini Embedding 2 Preview):

| Modality | Formats | Limits |
|----------|---------|--------|
| Text | paste / `.txt` | ~8,192 tokens (~6,000 words) |
| Image | PNG, JPEG | ≤ 6 images per upload request |
| Video | MP4, MOV | ≤ 120 seconds |
| Audio | MP3, WAV | ≤ 80 seconds |
| PDF | `.pdf` | ≤ 6 pages **per embed call**; longer PDFs are **auto-split** into 6-page segments |

---

## Stack

| Layer | Technology |
|-------|------------|
| Embeddings | `gemini-embedding-2-preview` (768-dim by default) |
| Generation | Gemini (`gemini-flash-latest` with fallbacks) |
| Vector DB | Pinecone (dense cosine index) |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Frontend | Next.js App Router, TypeScript, Tailwind CSS |
| Secrets | Root `.env` only (never commit real keys) |

---

## Repository layout

```
GeminiRAGproject/
├── .cursor/rules/          # Cursor project rules (architecture, RAG, frontend, security)
├── backend/
│   ├── app/
│   │   ├── api/            # /health, /api/upload, /api/chat, /api/media
│   │   ├── clients/        # Gemini + Pinecone wrappers
│   │   ├── core/           # config, logging, modality constants
│   │   ├── models/         # domain + API schemas
│   │   ├── pipelines/      # PDF split, ingest/enrich
│   │   ├── services/       # validation, storage, RAG orchestration
│   │   └── main.py
│   ├── uploads/            # persisted media (gitignored)
│   ├── requirements.txt
│   └── .venv/
├── frontend/
│   ├── app/                # Next.js App Router pages
│   ├── components/chat/    # ChatShell, Composer, Thread, citations
│   ├── lib/                # api.ts, attachments.ts, types.ts
│   └── package.json
├── tests/                  # pytest (validation, PDF split, API)
├── .env.example
└── README.md
```

---

## Architecture (high level)

```
┌─────────────┐     Upload      ┌──────────────────────────────────────┐
│  Next.js UI │ ──────────────► │ FastAPI  POST /api/upload            │
│  Upload btn │                 │  validate → enrich → embed → Pinecone│
└──────┬──────┘                 │  save file under backend/uploads/    │
       │ Send question          └──────────────────────────────────────┘
       │
       ▼
┌─────────────┐     Chat        ┌──────────────────────────────────────┐
│  Send btn   │ ──────────────► │ FastAPI  POST /api/chat              │
└─────────────┘                 │  retrieve → hydrate media → generate │
                                │  return answer + citations + file_url│
                                └──────────────────────────────────────┘
```

**Upload and chat are separate**

- **Upload** indexes files immediately (`POST /api/upload`)
- **Send** asks questions only (`POST /api/chat`) against already indexed content

---

## Prerequisites

- Python **3.11+**
- Node.js **18+** (LTS recommended)
- Gemini API key ([Google AI Studio](https://aistudio.google.com/))
- Pinecone API key and a **dense** cosine index (or let the app create `gemini-multimodal-rag`)

> Note: a sparse-only Pinecone index will fail dense Gemini embeddings. This project expects a dense index (768 dimensions by default).

---

## Setup

### 1. Clone / open the project

```bash
cd GeminiRAGproject
```

### 2. Environment variables

Copy the example env and fill in secrets:

```bash
cp .env.example .env
```

Required values in `.env`:

```env
GEMINI_API_KEY=your_gemini_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-2-preview
GEMINI_GENERATION_MODEL=gemini-flash-latest
EMBEDDING_DIMENSIONS=768

PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=gemini-multimodal-rag
PINECONE_NAMESPACE=default
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

APP_ENV=development
CORS_ORIGINS=http://localhost:3000
RAG_TOP_K=5

NEXT_PUBLIC_API_URL=http://localhost:8000
```

Frontend env (create if missing):

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

If port 8000 is busy on your machine, run the API on another port (e.g. 8001) and set `NEXT_PUBLIC_API_URL` to match.

### 3. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)  
API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 5. Tests

From the repo root (with backend venv active):

```bash
cd backend
pytest -q ../tests
```

---

## API reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Status + whether Gemini/Pinecone keys are configured |
| `POST` | `/api/upload` | Multipart `files` — validate, extract, embed, index, store |
| `POST` | `/api/chat` | Form `message` — retrieve + generate answer + citations |
| `GET` | `/api/media/{source_id}/{filename}` | Serve a stored uploaded file (e.g. image preview) |

### Upload response (example)

```json
{
  "indexed_count": 3,
  "message": "Uploaded and indexed 3 chunk(s) from report.pdf",
  "items": [
    {
      "source_id": "...",
      "title": "report.pdf",
      "modality": "pdf",
      "chunk_index": 0,
      "file_url": "/api/media/.../report.pages-1-6.pdf",
      "page_start": 1,
      "page_end": 6
    }
  ]
}
```

### Chat response (example)

```json
{
  "answer": "...",
  "indexed_count": 0,
  "citations": [
    {
      "source_id": "...",
      "modality": "image",
      "score": 0.85,
      "title": "IMG_2885.JPG",
      "text_preview": "Person wearing a red t-shirt...",
      "file_url": "/api/media/.../IMG_2885.JPG"
    }
  ]
}
```

---

## UI behavior

- ChatGPT-like shell: message thread + pinned composer
- **Upload** button / drag-and-drop → files upload and index immediately  
  Status: Checking → Uploading % → Indexing → Uploaded / Failed
- **Send** → text question only (no combined file+message submit)
- Assistant replies show **Sources** with modality, score, page ranges, and **image thumbnails** when `file_url` exists

---

## Ingest pipeline details

1. **Validate** — MIME/extension, size, duration, page count, batch limits  
2. **Segment** — PDFs longer than 6 pages split into sequential windows  
3. **Extract content**  
   - PDF → text via `pypdf`  
   - Image → Gemini visual/OCR description (on upload)  
   - Video/audio → describe deferred on upload (faster / fewer quota hits); transcribed/summarized when you ask  
4. **Embed** — Gemini Embedding 2 Preview via dedicated client  
5. **Store** — file saved under `backend/uploads/{source_id}/`  
6. **Index** — vectors + metadata (including `text_preview`, `file_url`, page ranges) in Pinecone  

Retrieval for image/video questions filters by modality when the query looks visual/video-related, then attaches matching media for multimodal generation when possible.

---

## Configuration notes

| Setting | Meaning |
|---------|---------|
| `EMBEDDING_DIMENSIONS` | Must match Pinecone index dimension (default `768`) |
| `GEMINI_GENERATION_MODEL` | Primary chat/describe model; code falls back if rate-limited |
| `DESCRIBE_MEDIA_ON_UPLOAD` | If `true`, also describe video/audio at upload time (slower, more quota) |
| `RAG_TOP_K` | Number of Pinecone matches returned |
| `MAX_UPLOAD_BYTES` | Max upload size (default 50 MB) |

---

## Typical usage

1. Start backend + frontend  
2. Click **Upload** and add images/PDFs/videos (wait until “Uploaded”)  
3. Ask questions with **Send**, e.g.  
   - “Show the person in the red t-shirt”  
   - “What does the paper say about attention?”  
   - “Show the video where someone wishes Mukesh and what they say”  

**Important:** Files uploaded *before* media persistence was added only have vectors/metadata. Re-upload those files once so descriptions and previews work.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Not Found` on upload | Stale API process without `/api/upload` | Restart uvicorn; confirm OpenAPI lists `/api/upload` |
| `Network error while uploading` | Large video + long processing, or connection drop | Retry; video describe is deferred on upload now |
| Gemini `429 RESOURCE_EXHAUSTED` | Free-tier generate quota | Wait and retry; switch `GEMINI_GENERATION_MODEL` or enable billing |
| Pinecone “dense vectors not supported” | Sparse index | Use/create dense cosine index (e.g. `gemini-multimodal-rag`) |
| Answers only see PDF text for image queries | Image not stored / thin metadata | Re-upload the image via **Upload** |
| Frontend can’t reach API | Wrong `NEXT_PUBLIC_API_URL` or port | Align frontend env with the port uvicorn actually uses |
| Port 8000 stuck on Windows | Dead process still LISTENING | Kill PIDs on 8000 or run API on `8001` and update `.env.local` |

---

## Security

- Never commit `.env` or real API keys  
- Only `NEXT_PUBLIC_API_URL` is exposed to the browser  
- Gemini and Pinecone keys stay on the backend  
- Uploaded binaries live in `backend/uploads/` (gitignored)

---

## Cursor rules

Project conventions live under `.cursor/rules/`:

- `project-architecture.mdc`
- `embedding-modality-specs.mdc`
- `rag-pipeline.mdc`
- `python-fastapi.mdc`
- `frontend-nextjs.mdc`
- `security-and-config.mdc`

---

## License

Private / internal use unless otherwise specified by the repository owner.
