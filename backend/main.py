from fastapi import FastAPI, UploadFile, File
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pdfminer.high_level import extract_text
from openai import OpenAI
from typing import List
import io
import json
import os
import re
import zipfile
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _extract_ranking_inputs(
    files: List[UploadFile], job_description_file: UploadFile | None
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    documents = []
    for file in files:
        content = await file.read()
        text = extract_text(io.BytesIO(content))
        documents.append({"filename": file.filename, "text": text})

    job_description_text = "Not provided."
    job_description_filename = None
    if job_description_file is not None:
        jd_content = await job_description_file.read()
        job_description_text = extract_text(io.BytesIO(jd_content)).strip() or "Not provided."
        job_description_filename = job_description_file.filename

    return documents, job_description_text, job_description_filename


def _ranking_messages(documents, job_description_text):
    return [
        {
            "role": "system",
            "content": (
                "You are an AI recruiter assistant. Rank candidate resumes from strongest to weakest. "
                "Do NOT rank the job description as a candidate. "
                "For each file, provide a score from 0 to 100 and a short reason based on the job description. Include some parts of the resume that are relevant to the job description. "
                "Then provide a final recommendation."
            ),
        },
        {
            "role": "user",
            "content": (
                "Use the job description as criteria context only (if provided), and rank only candidates.\n\n"
                f"Job Description Context:\n{job_description_text}\n\n"
                f"Candidate Resumes:\n{json.dumps(documents)}"
            ),
        },
    ]


def _safe_filename(raw: str) -> str:
    normalized = re.sub(r"\s+", " ", raw).strip()
    cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", normalized)
    return cleaned.replace(" ", "-") or "optimized-resume"


def _strip_markdown_inline(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", cleaned)
    cleaned = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _markdown_to_pdf_blocks(content: str):
    blocks = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            blocks.append({"text": "", "type": "blank"})
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            blocks.append(
                {
                    "text": _strip_markdown_inline(heading.group(2)),
                    "type": "heading",
                    "level": len(heading.group(1)),
                }
            )
            continue

        bullet = re.match(r"^[-*+]\s+(.*)$", line) or re.match(r"^\d+[.)]\s+(.*)$", line)
        if bullet:
            blocks.append({"text": _strip_markdown_inline(bullet.group(1)), "type": "bullet"})
            continue

        blocks.append({"text": _strip_markdown_inline(line), "type": "paragraph"})

    return blocks


def _render_text_pdf(content: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    left = 56
    top = height - 56
    max_width = width - (left * 2)
    y = top
    min_y = 56

    def ensure_space(font_size: int, line_height: int):
        nonlocal y
        if y <= min_y:
            c.showPage()
            y = top
        c.setFont("Times-Roman", font_size)

    def draw_wrapped_line(text: str, font_name: str, font_size: int, line_height: int, indent: int = 0):
        nonlocal y
        if not text:
            y -= line_height
            return

        c.setFont(font_name, font_size)
        words = text.split()
        current = ""
        available_width = max_width - indent
        x = left + indent

        for word in words:
            candidate = word if not current else f"{current} {word}"
            if c.stringWidth(candidate, font_name, font_size) <= available_width:
                current = candidate
                continue

            ensure_space(font_size, line_height)
            c.setFont(font_name, font_size)
            c.drawString(x, y, current)
            y -= line_height
            current = word

        if current:
            ensure_space(font_size, line_height)
            c.setFont(font_name, font_size)
            c.drawString(x, y, current)
            y -= line_height

    for block in _markdown_to_pdf_blocks(content):
        block_type = block["type"]
        text = block.get("text", "")

        if block_type == "blank":
            y -= 8
            if y <= min_y:
                c.showPage()
                y = top
            continue

        if block_type == "heading":
            level = block.get("level", 2)
            font_size = 15 if level == 1 else 13 if level == 2 else 12
            draw_wrapped_line(text.upper(), "Times-Bold", font_size, line_height=16)
            y -= 2
            continue

        if block_type == "bullet":
            draw_wrapped_line(f"• {text}", "Times-Roman", 11, line_height=14, indent=10)
            continue

        draw_wrapped_line(text, "Times-Roman", 11, line_height=14)

    c.save()
    buffer.seek(0)
    return buffer.read()


def _build_optimization_messages(resume_documents, job_description_text):
    return [
        {
            "role": "system",
            "content": (
                "You are an expert resume writer. Create one ATS-optimized resume tailored to the provided "
                "job description. Use details from the candidate resume source texts only; do not invent "
                "employers, degrees, or dates. Return valid JSON only with this schema: "
                '{"candidate_name":"string","job_title":"string","optimized_resume":"string"}. '
                "The optimized_resume field should be plain text with clear section headers and bullet points."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Job Description:\n{job_description_text}\n\n"
                f"Candidate Source Resumes:\n{json.dumps(resume_documents)}"
            ),
        },
    ]


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}


@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text = extract_text(io.BytesIO(content))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a AI Recruiter Assistant. Your task is to help the user with ranking the job applications based on the resume and the job description. Provide a score between 0 and 100 for the application."},
            {"role": "user", "content": text},
        ],
    )
    answer = response.choices[0].message.content
    return {
        "message": "File uploaded successfully",
        "filename": file.filename,
        "text": text,
        "answer": answer,
    }


@app.post("/upload-files")
async def upload_files(files: List[UploadFile] = File(...)):
    documents = []
    for file in files:
        content = await file.read()
        text = extract_text(io.BytesIO(content))
        documents.append({"filename": file.filename, "text": text})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI recruiter assistant. Compare all resumes together and rank "
                    "them from strongest to weakest. Return valid JSON only with this shape: "
                    '{"ranked_candidates":[{"filename":"string","score":0-100,'
                    '"reason":"short reason"}],"summary":"string"}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    "Here are the extracted resume texts. Rank them comparatively.\n\n"
                    f"{json.dumps(documents)}"
                ),
            },
        ],
    )
    combined_answer = response.choices[0].message.content

    return {
        "message": "Files uploaded successfully",
        "documents": documents,
        "filenames": [file.filename for file in files],
        "texts": [document["text"] for document in documents],
        "answer": combined_answer,
    }


@app.post("/rank-applications")
async def rank_applications(
    files: List[UploadFile] = File(...),
    job_description_file: UploadFile | None = File(None),
):
    documents, job_description_text, job_description_filename = await _extract_ranking_inputs(
        files, job_description_file
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=_ranking_messages(documents, job_description_text),
    )
    answer = response.choices[0].message.content

    return {
        "message": "Applications ranked successfully",
        "filenames": [file.filename for file in files],
        "ranked_candidate_filenames": [doc["filename"] for doc in documents],
        "job_description_filename": job_description_filename,
        "answer": answer,
    }


@app.post("/rank-applications/stream")
async def rank_applications_stream(
    files: List[UploadFile] = File(...),
    job_description_file: UploadFile | None = File(None),
):
    documents, job_description_text, _ = await _extract_ranking_inputs(files, job_description_file)

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=_ranking_messages(documents, job_description_text),
        stream=True,
    )

    def generate():
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/optimize-resumes/download")
async def optimize_resumes_download(
    files: List[UploadFile] = File(...),
    job_description_files: List[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one base resume PDF.")
    if not job_description_files:
        raise HTTPException(status_code=400, detail="Upload at least one job description PDF.")

    resume_documents = []
    for file in files:
        content = await file.read()
        text = extract_text(io.BytesIO(content)).strip()
        if text:
            resume_documents.append({"filename": file.filename, "text": text})

    if not resume_documents:
        raise HTTPException(status_code=400, detail="Could not extract readable text from resumes.")

    zip_buffer = io.BytesIO()
    created_count = 0
    candidate_name_for_archive = ""

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for job_file in job_description_files:
            jd_bytes = await job_file.read()
            jd_text = extract_text(io.BytesIO(jd_bytes)).strip()
            if not jd_text:
                continue

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=_build_optimization_messages(resume_documents, jd_text),
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)

            candidate_name = str(parsed.get("candidate_name", "candidate")).strip() or "candidate"
            job_title = str(parsed.get("job_title", "optimized-role")).strip() or "optimized-role"
            optimized_resume = str(parsed.get("optimized_resume", "")).strip()
            if not optimized_resume:
                continue

            if not candidate_name_for_archive:
                candidate_name_for_archive = candidate_name
            filename = f"{_safe_filename(job_title)}-{_safe_filename(candidate_name)}.pdf"
            pdf_bytes = _render_text_pdf(optimized_resume)
            zf.writestr(filename, pdf_bytes)
            created_count += 1

    if created_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No optimized resumes were generated. Check that your PDFs contain extractable text.",
        )

    zip_buffer.seek(0)
    archive_name = f"optimized-resumes-{_safe_filename(candidate_name_for_archive)}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{archive_name}"'}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)