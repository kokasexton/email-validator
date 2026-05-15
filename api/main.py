import asyncio
import csv
import io
import os
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client, Client

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_validator.batch import validate_single, validate_batch, read_csv_rows, EmailInput

SUPABASE_URL = os.environ.get("VITE_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("VITE_SUPABASE_SUPABASE_ANON_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

_supabase: Optional[Client] = None

def get_db() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


app = FastAPI(
    title="VerifyPro Email Validation API",
    description="Enterprise email validation — syntax, disposable, DNS/MX, and SMTP checks.",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SingleRequest(BaseModel):
    email: str
    skip_smtp: bool = False


class BulkRequest(BaseModel):
    emails: list[str]
    skip_smtp: bool = False


def _r(result) -> dict:
    return {
        "email": result.email,
        "status": result.status,
        "score": result.score,
        "failure_reason": result.failure_reason,
        "regexp": result.regexp,
        "gibberish": result.gibberish,
        "disposable": result.disposable,
        "webmail": result.webmail,
        "role_based": result.role_based,
        "mx_records": result.mx_records,
        "smtp_check": result.smtp_check,
        "accept_all": result.accept_all,
        "block": result.block,
        "smtp_server": result.smtp_server,
        "error": result.error,
    }


def _summary(results) -> dict:
    return {
        "valid": sum(1 for r in results if r.status == "valid"),
        "invalid": sum(1 for r in results if r.status == "invalid"),
        "accept_all": sum(1 for r in results if r.status == "accept_all"),
        "unknown": sum(1 for r in results if r.status == "unknown"),
    }


async def _save_job(results, job_type: str, filename: Optional[str] = None) -> str:
    db = get_db()
    s = _summary(results)
    job = db.table("validation_jobs").insert({
        "job_type": job_type,
        "status": "completed",
        "total_emails": len(results),
        "processed_emails": len(results),
        "valid_count": s["valid"],
        "invalid_count": s["invalid"],
        "accept_all_count": s["accept_all"],
        "unknown_count": s["unknown"],
        **({"original_filename": filename} if filename else {}),
    }).execute()
    job_id = job.data[0]["id"]
    rows = [{"job_id": job_id, "email": r.email, "status": r.status, "score": r.score,
             "failure_reason": r.failure_reason, "regexp": r.regexp, "gibberish": r.gibberish,
             "disposable": r.disposable, "webmail": r.webmail, "role_based": r.role_based,
             "mx_records": r.mx_records, "smtp_check": r.smtp_check, "accept_all": r.accept_all,
             "block": r.block, "smtp_server": r.smtp_server} for r in results]
    if rows:
        db.table("validation_results").insert(rows).execute()
    return job_id


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/validate/single")
async def validate_single_email(req: SingleRequest):
    """Validate a single email address with full checks."""
    result = await validate_single(req.email.strip(), skip_smtp=req.skip_smtp)
    job_id = await _save_job([result], "single")
    return {"job_id": job_id, "result": _r(result)}


@app.post("/api/validate/bulk")
async def validate_bulk(req: BulkRequest):
    """Validate up to 500 emails supplied as a JSON array."""
    if len(req.emails) > 500:
        raise HTTPException(400, "Maximum 500 emails per bulk request. Use CSV for larger batches.")
    inputs = [EmailInput(email=e.strip(), source_row={}, row_number=i) for i, e in enumerate(req.emails)]
    results = await validate_batch(inputs, skip_smtp=req.skip_smtp)
    job_id = await _save_job(results, "batch")
    return {"job_id": job_id, "total": len(results), "results": [_r(r) for r in results], "summary": _summary(results)}


@app.post("/api/validate/csv")
async def validate_csv(
    file: UploadFile = File(...),
    skip_smtp: bool = Query(False),
    email_column: Optional[str] = Query(None),
):
    """Upload a CSV file and validate all email addresses found."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted.")
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except Exception:
        raise HTTPException(422, "Could not decode file as UTF-8.")
    try:
        inputs = read_csv_rows(io.StringIO(text), email_column=email_column)
    except Exception as e:
        raise HTTPException(422, f"CSV parsing error: {e}")
    if len(inputs) > 10000:
        raise HTTPException(400, "Maximum 10,000 rows per upload.")
    results = await validate_batch(inputs, skip_smtp=skip_smtp)
    job_id = await _save_job(results, "batch", filename=file.filename)
    return {"job_id": job_id, "total": len(results), "filename": file.filename,
            "results": [_r(r) for r in results], "summary": _summary(results)}


@app.get("/api/validate/csv/{job_id}/download")
async def download_csv(job_id: str):
    """Download validation results for a job as a CSV file."""
    db = get_db()
    resp = db.table("validation_results").select("*").eq("job_id", job_id).execute()
    if not resp.data:
        raise HTTPException(404, "No results found for this job.")
    fields = ["email", "status", "score", "failure_reason", "regexp", "gibberish",
              "disposable", "webmail", "role_based", "mx_records", "smtp_check",
              "accept_all", "block", "smtp_server"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(resp.data)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=results-{job_id[:8]}.csv"},
    )


@app.get("/api/jobs")
async def list_jobs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """List recent validation jobs."""
    db = get_db()
    resp = db.table("validation_jobs").select("*").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return {"jobs": resp.data, "total": len(resp.data)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job and all its results."""
    db = get_db()
    job = db.table("validation_jobs").select("*").eq("id", job_id).maybeSingle().execute()
    if not job.data:
        raise HTTPException(404, "Job not found.")
    results = db.table("validation_results").select("*").eq("job_id", job_id).execute()
    return {"job": job.data, "results": results.data}
