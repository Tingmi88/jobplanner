"""
FastAPI routes for the JobPlanner application.
"""
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.graph_runtime import planner_agent
from app.tools import parse_job_description, save_job_description
import time, logging, json, uuid
from app.logging_setup import setup_logging, RequestIdFilter

setup_logging()  
logger = logging.getLogger("jobplanner.api")

app = FastAPI(title="JobPlanner API")

class PlanIn(BaseModel):
    user_input: str

class SaveJobIn(BaseModel):
    job_description: str

class PlanWithJobIn(BaseModel):
    job_description: str
    user_input: Optional[str] = None

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/plan")
def plan(payload: PlanIn):
    initial_input = {
        "user_input": payload.user_input,
        "intermediate_messages": [],
        "messages": []
    }
    result = planner_agent.invoke(initial_input)
    return {
        "final_output": result.get("final_output"),
        "intermediate_messages": result.get("intermediate_messages", []),
    }


@app.post("/save-job")
def save_job(payload: SaveJobIn):
    """Parse and save a job description from raw text."""
    try:
        # Parse the job description
        job_data = parse_job_description(payload.job_description)
        
        # Save to file
        filename = save_job_description(job_data)
        
        return {
            "success": True,
            "filename": filename,
            "job_data": job_data
        }
    except Exception as e:
        logger.exception("Failed to save job description")
        raise HTTPException(status_code=400, detail=f"Failed to parse or save job description: {str(e)}")


@app.post("/plan-with-job")
def plan_with_job(payload: PlanWithJobIn):
    """Save a job description and generate a plan using it."""
    try:
        # Parse and save the job description
        job_data = parse_job_description(payload.job_description)
        filename = save_job_description(job_data)
        
        # Generate user input if not provided
        if payload.user_input:
            user_input = payload.user_input
        else:
            # Default: create a plan for this specific job
            title = job_data.get('title', 'this position')
            company = job_data.get('company', 'this company')
            # Use filename for more reliable loading, or provide both options
            user_input = f"Create a learning and preparation plan for the {title} position at {company}. First, load the job description using get_job_by_filename(\"{filename}\") or load_job_by_title(\"{title}\") or list_all_jobs() to find it, then analyze the requirements and create a comprehensive plan."
        
        # Generate the plan
        initial_input = {
            "user_input": user_input,
            "intermediate_messages": [],
            "messages": []
        }
        result = planner_agent.invoke(initial_input)
        
        return {
            "success": True,
            "filename": filename,
            "job_data": job_data,
            "final_output": result.get("final_output"),
            "intermediate_messages": result.get("intermediate_messages", []),
        }
    except Exception as e:
        logger.exception("Failed to save job and generate plan")
        raise HTTPException(status_code=400, detail=f"Failed to process: {str(e)}")


@app.get("/", response_class=HTMLResponse)
def root():
    return """
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JobPlanner · Demo</title>
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; max-width: 900px; }
  h1 { font-size: 1.4rem; margin: 0 0 1rem; }
  textarea { width: 100%; height: 160px; padding: .75rem; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  button { padding: .6rem 1rem; border: 0; border-radius: .5rem; background: #111827; color: #fff; cursor: pointer; }
  button[disabled] { opacity: .6; cursor: progress; }
  .row { display: grid; gap: .75rem; margin: 1rem 0; }
  .card { border: 1px solid #e5e7eb; border-radius: .75rem; padding: 1rem; background: #fff; }
  .muted { color: #6b7280; font-size: .9rem; }
  pre { white-space: pre-wrap; word-break: break-word; }
  .footer { margin-top: 2rem; font-size: .85rem; color: #6b7280; }
</style>
<h1>JobPlanner API — Browser Demo</h1>

<div class="card">
  <h2 style="font-size: 1.1rem; margin: 0 0 1rem;">Option 1: Paste Job Description</h2>
  <label for="jobDesc" class="muted">Paste a job description below. The system will extract title, company, and requirements, then save it.</label>
  <div class="row">
    <textarea id="jobDesc" placeholder="Paste job description here…" style="height: 200px;"></textarea>
    <div class="row" style="grid-auto-flow: column; justify-content: start; gap: 0.5rem;">
      <button id="saveJob">Save Job</button>
      <button id="saveAndPlan">Save & Generate Plan</button>
      <span id="jobElapsed" class="muted"></span>
    </div>
  </div>
  <div id="jobResult" style="margin-top: 1rem; padding: 0.75rem; background: #f9fafb; border-radius: 0.5rem; display: none;">
    <div class="muted" style="margin-bottom: 0.5rem;">Job Saved:</div>
    <pre id="jobResp" style="margin: 0; font-size: 0.9rem;">—</pre>
  </div>
</div>

<div class="card" style="margin-top: 1rem;">
  <h2 style="font-size: 1.1rem; margin: 0 0 1rem;">Option 2: General Plan Request</h2>
  <label for="jd" class="muted">Enter a prompt (e.g., "Generate a 7-day learning plan for a Data Scientist focusing on Python & ML.")</label>
  <div class="row">
    <textarea id="jd" placeholder="Type your request here…">Generate a 7-day learning plan for a Data Scientist focusing on Python & ML.</textarea>
    <div class="row" style="grid-auto-flow: column; justify-content: start;">
      <button id="go">Generate Plan</button>
      <span id="elapsed" class="muted"></span>
    </div>
  </div>
</div>

<div id="out" class="card" style="margin-top:1rem;">
  <div class="muted">Response</div>
  <pre id="resp">—</pre>
</div>

<div class="footer">
  Try the API directly at <a href="/docs">/docs</a> or <code>/health</code>.
</div>

<script>
const btn = document.getElementById('go');
const ta  = document.getElementById('jd');
const pre = document.getElementById('resp');
const elapsed = document.getElementById('elapsed');

const saveJobBtn = document.getElementById('saveJob');
const saveAndPlanBtn = document.getElementById('saveAndPlan');
const jobDesc = document.getElementById('jobDesc');
const jobElapsed = document.getElementById('jobElapsed');
const jobResult = document.getElementById('jobResult');
const jobResp = document.getElementById('jobResp');

// Save job description
saveJobBtn.addEventListener('click', async () => {
  const description = jobDesc.value.trim();
  if (!description) { alert('Please paste a job description.'); return; }

  saveJobBtn.disabled = true; saveAndPlanBtn.disabled = true;
  jobElapsed.textContent = 'Parsing and saving…';
  jobResult.style.display = 'none';
  jobResp.textContent = '…';

  const t0 = performance.now();
  try {
    const res = await fetch('/save-job', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: description })
    });

    const msHeader = res.headers.get('x-elapsed-ms');
    jobElapsed.textContent = msHeader ? `Server time: ${msHeader} ms` : '';

    if (!res.ok) {
      const txt = await res.text();
      jobResp.textContent = `Error ${res.status}: ${txt}`;
      jobResult.style.display = 'block';
      return;
    }

    const data = await res.json();
    jobResp.textContent = `✓ Saved as: ${data.filename}.json\n\nTitle: ${data.job_data.title}\nCompany: ${data.job_data.company}\nLocation: ${data.job_data.location || 'Not specified'}\nRequirements: ${data.job_data.requirements.length} items`;
    jobResult.style.display = 'block';
  } catch (e) {
    jobResp.textContent = 'Network error: ' + e;
    jobResult.style.display = 'block';
  } finally {
    const dt = Math.round(performance.now() - t0);
    jobElapsed.textContent += (jobElapsed.textContent ? ' · ' : '') + `Client time: ${dt} ms`;
    saveJobBtn.disabled = false;
    saveAndPlanBtn.disabled = false;
  }
});

// Save job and generate plan
saveAndPlanBtn.addEventListener('click', async () => {
  const description = jobDesc.value.trim();
  if (!description) { alert('Please paste a job description.'); return; }

  saveJobBtn.disabled = true; saveAndPlanBtn.disabled = true;
  jobElapsed.textContent = 'Saving job and generating plan…';
  jobResult.style.display = 'none';
  jobResp.textContent = '…';
  pre.textContent = 'Generating plan…';

  const t0 = performance.now();
  try {
    const res = await fetch('/plan-with-job', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: description })
    });

    const msHeader = res.headers.get('x-elapsed-ms');
    jobElapsed.textContent = msHeader ? `Server time: ${msHeader} ms` : '';

    if (!res.ok) {
      const txt = await res.text();
      jobResp.textContent = `Error ${res.status}: ${txt}`;
      jobResult.style.display = 'block';
      return;
    }

    const data = await res.json();
    jobResp.textContent = `✓ Saved as: ${data.filename}.json\n\nTitle: ${data.job_data.title}\nCompany: ${data.job_data.company}`;
    jobResult.style.display = 'block';
    
    // Show the plan in the main output area
    pre.textContent = data.final_output ? data.final_output : JSON.stringify(data, null, 2);
    elapsed.textContent = msHeader ? `Server time: ${msHeader} ms` : '';
  } catch (e) {
    jobResp.textContent = 'Network error: ' + e;
    jobResult.style.display = 'block';
    pre.textContent = 'Network error: ' + e;
  } finally {
    const dt = Math.round(performance.now() - t0);
    jobElapsed.textContent += (jobElapsed.textContent ? ' · ' : '') + `Client time: ${dt} ms`;
    elapsed.textContent += (elapsed.textContent ? ' · ' : '') + `Client time: ${dt} ms`;
    saveJobBtn.disabled = false;
    saveAndPlanBtn.disabled = false;
  }
});

// Original plan generation
btn.addEventListener('click', async () => {
  const user_input = ta.value.trim();
  if (!user_input) { alert('Please enter a prompt.'); return; }

  btn.disabled = true; elapsed.textContent = 'Running…';
  pre.textContent = '…';

  const t0 = performance.now();
  try {
    const res = await fetch('/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_input })
    });

    const msHeader = res.headers.get('x-elapsed-ms');
    elapsed.textContent = msHeader ? `Server time: ${msHeader} ms` : '';

    if (!res.ok) {
      const txt = await res.text();
      pre.textContent = `Error ${res.status}: ${txt}`;
      return;
    }

    const data = await res.json();
    // Prefer final_output (markdown-ish), fall back to whole JSON
    pre.textContent = data.final_output ? data.final_output : JSON.stringify(data, null, 2);
  } catch (e) {
    pre.textContent = 'Network error: ' + e;
  } finally {
    const dt = Math.round(performance.now() - t0);
    elapsed.textContent += (elapsed.textContent ? ' · ' : '') + `Client time: ${dt} ms`;
    btn.disabled = false;
  }
});
</script>
</html>
"""


@app.middleware("http")
async def timing_and_requestid(request: Request, call_next):
    start = time.time()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    # attach request_id to all logs on this request
    req_logger = logging.LoggerAdapter(logger, {"request_id": request_id})
    try:
        resp = await call_next(request)
        resp.headers["X-Elapsed-ms"] = str(int((time.time() - start) * 1000))
        resp.headers["X-Request-Id"] = request_id
        req_logger.info("request complete", extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": resp.status_code,
        })
        return resp
    except Exception as e:
        req_logger.exception("request error", extra={
            "path": request.url.path, "method": request.method
        })
        raise
