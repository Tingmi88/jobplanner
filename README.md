# JobPlanner

An intelligent job planning and execution system built with FastAPI and LangGraph.

## Features

- **Intelligent Job Planning**: AI-powered job search and planning using LangGraph
- **FastAPI Backend**: RESTful API for job planning operations
- **Job Data Management**: Structured storage and retrieval of job descriptions
- **Docker Support**: Containerized deployment ready
- **Cloud Deployment**: Ready for deployment on Render.com

## Project Structure

```
jobplanner/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── api.py               # FastAPI routes and endpoints
│   ├── graph_runtime.py     # LangGraph workflow runtime
│   ├── tools.py             # Job search and data access tools
│   ├── nodes.py             # Graph nodes (planner, executor, synthesizer, router)
│   └── settings.py          # Configuration and environment variables
├── data/
│   └── jobs/                # JSON job description files
├── infra/
│   ├── Dockerfile           # Docker container configuration
│   └── render.yaml          # Render.com deployment configuration
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd jobplanner
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

4. Add job data:
   - Place JSON job description files in `data/jobs/`
   - Each file should contain job details (title, company, description, etc.)

5. Run the application:
```bash
python -m uvicorn app.api:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /plan` - Create a job plan
- `GET /jobs` - List all available jobs
- `GET /jobs/{job_id}` - Get specific job details

## Usage

### Creating a Job Plan

```bash
curl -X POST "http://localhost:8000/plan" \
     -H "Content-Type: application/json" \
     -d '{"user_input": "I want to find software engineering jobs"}'
```

### Listing Jobs

```bash
curl "http://localhost:8000/jobs"
```

## Configuration

Environment variables:

- `OPENAI_API_KEY` - Required: Your OpenAI API key
- `LLM_MODEL` - Optional: LLM model to use (default: gpt-3.5-turbo)
- `LLM_TEMPERATURE` - Optional: LLM temperature (default: 0.7)
- `DATA_DIR` - Optional: Data directory path (default: data)
- `LOG_LEVEL` - Optional: Logging level (default: INFO)

## Deployment

### Docker

```bash
docker build -f infra/Dockerfile -t jobplanner .
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key jobplanner
```

### Render.com

1. Connect your repository to Render
2. Use the `infra/render.yaml` configuration
3. Set your `OPENAI_API_KEY` environment variable
4. Deploy!

## Development

### Adding New Job Data

1. Create JSON files in `data/jobs/`
2. Each file should contain:
```json
{
  "title": "Software Engineer",
  "company": "Tech Corp",
  "description": "Job description...",
  "requirements": ["Python", "FastAPI"],
  "location": "Remote",
  "salary": "$100k-150k"
}
```

### Extending the Graph

The LangGraph workflow can be extended by:
1. Adding new nodes in `app/nodes.py`
2. Modifying the graph structure in `app/graph_runtime.py`
3. Adding new tools in `app/tools.py`

## License

MIT License

