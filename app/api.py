"""
FastAPI routes for the JobPlanner application.
"""
from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.graph_runtime import planner_agent
import time, logging, json, uuid
from app.logging_setup import setup_logging, RequestIdFilter

setup_logging()  # call once at import time
logger = logging.getLogger("jobplanner.api")

app = FastAPI(title="JobPlanner API")

class PlanIn(BaseModel):
    user_input: str

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <h2>JobPlanner API</h2>
    <p>Try <a href="/docs">/docs</a> for the interactive API, or <code>/health</code>.</p>
    """

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
