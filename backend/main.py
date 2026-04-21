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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)