import os
from dotenv import load_dotenv
load_dotenv(override=True)

REQUIRED = ["NEBIUS_API_KEY", "TAVILY_API_KEY"] 
for k in REQUIRED:
    if not os.environ.get(k):
        raise RuntimeError(f"Missing env var: {k}")
