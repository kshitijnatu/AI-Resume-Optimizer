# AI Resume Ranker

AI Resume Ranker is a full-stack app that:
- uploads candidate resume PDFs
- optionally uploads one job description PDF
- extracts text from PDFs on the backend
- sends content to OpenAI for comparative ranking
- streams the ranking response back to the frontend in real time

## Tech Stack

- Frontend: React + Vite
- Backend: FastAPI + Python 3.12+
- PDF extraction: `pdfminer.six`
- LLM: OpenAI Chat Completions (`gpt-4o-mini`)

## Project Structure

```text
.
├── backend/
│   ├── main.py
│   ├── pyproject.toml
│   └── uv.lock
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   └── api/api.js
    └── package.json
```

## Prerequisites

- Python 3.12+
- Node.js 18+ (or newer LTS)
- `uv` installed ([uv docs](https://docs.astral.sh/uv/))
- OpenAI API key

## Environment Variables

Create `backend/.env` with:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

The backend reads `OPENAI_API_KEY` via `os.getenv`.

## Run the Backend

From project root:

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`.

## Run the Frontend

In a second terminal, from project root:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

## How to Use

1. Open the frontend in your browser (`http://localhost:5173`).
2. Upload candidate resumes using:
   - **Single resume** input and/or
   - **Multiple resumes** input.
3. (Optional) Upload one **Job description** PDF.
4. Click **Rank Applications**.
5. Watch the response stream live in the Response panel.

## Current Ranking Behavior

- Only files uploaded in resume inputs are ranked as candidates.
- Job description file is treated as scoring context only.
- If no job description is uploaded, the model ranks resumes using general criteria.

## API Endpoints

### `GET /`
Health/test route.

### `POST /rank-applications`
Returns non-streaming ranking response.

Multipart form fields:
- `files`: one or many candidate resume PDFs (required)
- `job_description_file`: one job description PDF (optional)

### `POST /rank-applications/stream`
Returns streaming plain-text ranking response.

Multipart form fields:
- `files`: one or many candidate resume PDFs (required)
- `job_description_file`: one job description PDF (optional)

Response type:
- `text/plain` stream (chunked)

### Legacy Routes

These routes still exist for earlier flow/testing:
- `POST /upload-file`
- `POST /upload-files`

## Notes

- CORS is configured in backend for `http://localhost:5173`.
- The frontend uses `react-markdown` to render model output.
- Streaming is implemented with:
  - FastAPI `StreamingResponse` on backend
  - `fetch(...).body.getReader()` on frontend

## Troubleshooting

- **`No files uploaded.`**
  - Upload at least one candidate resume PDF before ranking.

- **OpenAI auth errors**
  - Check `OPENAI_API_KEY` in `backend/.env`.
  - Restart backend after changing env values.

- **CORS/network errors**
  - Confirm backend is running at `http://localhost:8000`.
  - Confirm frontend is running at `http://localhost:5173`.

- **No/poor PDF text extraction**
  - Some scanned PDFs may not contain selectable text.
  - Use machine-readable PDFs when possible.
