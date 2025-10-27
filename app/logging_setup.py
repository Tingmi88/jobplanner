# app/logging_setup.py
import logging, sys, uuid
from pythonjsonlogger import jsonlogger

def setup_logging(level="INFO"):
    handler = logging.StreamHandler(sys.stdout)
    fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
    )
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    # Remove uvicorn's default handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

class RequestIdFilter(logging.Filter):
    def __init__(self, request_id=None):
        super().__init__()
        self.request_id = request_id or "-"

    def filter(self, record):
        # add request_id attribute if missing
        if not hasattr(record, "request_id"):
            record.request_id = self.request_id
        return True
