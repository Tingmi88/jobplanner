"""
FastAPI routes for the JobPlanner application.
"""
from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.graph_runtime import planner_agent
import time, logging, json, uuid
from app.logging_setup import setup_logging, RequestIdFilter

setup_logging()  
logger = logging.getLogger("jobplanner.api")

app = FastAPI(title="JobPlanner API")

class PlanIn(BaseModel):
    user_input: str

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
  <label for="jd" class="muted">Enter a prompt (e.g., “Generate a 7-day learning plan for a Data Scientist focusing on Python & ML.”)</label>
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
