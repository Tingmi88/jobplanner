"""
Tool functions for job search and data access.
"""

from langchain.tools import tool
from pathlib import Path
import json

JOBS_DIR = Path("data/jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)

@tool
def load_job_by_title(job_title: str) -> str:
    """Load a job description by job title from the jobs directory"""
    # Search for files that contain the job title in their filename
    job_files = list(JOBS_DIR.glob("*.json"))
    
    for job_file in job_files:
        # Check if job title matches filename (case-insensitive)
        if job_title.lower() in job_file.stem.lower():
            with open(job_file, 'r') as f:
                job_data = json.load(f)
            return f"""Job: {job_data.get('title', 'Unknown')}
Company: {job_data.get('company', 'Unknown')}
Location: {job_data.get('location', 'Unknown')}
Description: {job_data.get('description', '')}
Requirements: {', '.join(job_data.get('requirements', []))}
Responsibilities: {', '.join(job_data.get('responsibilities', []))}
Salary: {job_data.get('salary_range', 'Not specified')}
Employment Type: {job_data.get('employment_type', 'Not specified')}
Experience Level: {job_data.get('experience_level', 'Not specified')}"""
    
    return f"Job with title '{job_title}' not found in directory"

@tool
def search_jobs_by_title(job_title: str) -> str:
    """Search for jobs by partial title match"""
    matching_jobs = []
    job_files = list(JOBS_DIR.glob("*.json"))
    
    for job_file in job_files:
        with open(job_file, 'r') as f:
            job_data = json.load(f)
        
        # Check if job title contains the search term
        if job_title.lower() in job_data.get('title', '').lower():
            matching_jobs.append(f"- {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')} (File: {job_file.stem})")
    
    return f"Jobs matching '{job_title}':\n" + "\n".join(matching_jobs) if matching_jobs else f"No jobs found matching '{job_title}'"

@tool
def list_all_jobs() -> str:
    """List all available jobs with their titles and companies"""
    job_files = list(JOBS_DIR.glob("*.json"))
    if not job_files:
        return "No jobs found in directory"
    
    jobs = []
    for job_file in job_files:
        with open(job_file, 'r') as f:
            job_data = json.load(f)
        jobs.append(f"- {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')} (File: {job_file.stem})")
    
    return "Available jobs:\n" + "\n".join(jobs)

@tool
def get_job_by_filename(filename: str) -> str:
    """Get job details by exact filename (without .json extension)"""
    job_file = JOBS_DIR / f"{filename}.json"
    if job_file.exists():
        with open(job_file, 'r') as f:
            job_data = json.load(f)
        return f"""Job: {job_data.get('title', 'Unknown')}
Company: {job_data.get('company', 'Unknown')}
Location: {job_data.get('location', 'Unknown')}
Description: {job_data.get('description', '')}
Requirements: {', '.join(job_data.get('requirements', []))}
Responsibilities: {', '.join(job_data.get('responsibilities', []))}
Salary: {job_data.get('salary_range', 'Not specified')}
Employment Type: {job_data.get('employment_type', 'Not specified')}
Experience Level: {job_data.get('experience_level', 'Not specified')}"""
    else:
        return f"Job file '{filename}.json' not found"

@tool
def search_jobs_by_criteria(criteria: str) -> str:
    """Search jobs by specific criteria (skills, location, etc.)"""
    matching_jobs = []
    for job_file in JOBS_DIR.glob("*.json"):
        with open(job_file, 'r') as f:
            job_data = json.load(f)
        
        # Search in title, description, requirements, and responsibilities
        searchable_text = f"{job_data.get('title', '')} {job_data.get('description', '')} {job_data.get('location', '')} {' '.join(job_data.get('requirements', []))} {' '.join(job_data.get('responsibilities', []))}".lower()
        
        if any(keyword.lower() in searchable_text for keyword in criteria.split()):
            matching_jobs.append(f"- {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')} (File: {job_file.stem})")
    
    return f"Jobs matching '{criteria}':\n" + "\n".join(matching_jobs) if matching_jobs else f"No jobs found matching '{criteria}'"