"""
Tool functions for job search and data access.
"""

from langchain.tools import tool
from pathlib import Path
import json
import os
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_nebius import ChatNebius
from dotenv import load_dotenv

load_dotenv(override=True)

JOBS_DIR = Path("data/jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize LLM for parsing job descriptions
_llm = None
def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatNebius(model="Qwen/Qwen3-14B", api_key=os.environ.get("NEBIUS_API_KEY"))
    return _llm

class JobDescription(BaseModel):
    """Structured job description extracted from raw text."""
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    description: str = Field(description="Job description text")
    requirements: list[str] = Field(default_factory=list, description="List of requirements")
    location: Optional[str] = Field(default=None, description="Job location")
    salary: Optional[str] = Field(default=None, description="Salary or salary range")
    type: Optional[str] = Field(default=None, description="Employment type (Full-time, Part-time, etc.)")
    posted_date: Optional[str] = Field(default=None, description="Posted date in YYYY-MM-DD format")
    benefits: list[str] = Field(default_factory=list, description="List of benefits")
    responsibilities: list[str] = Field(default_factory=list, description="List of responsibilities")


def sanitize_filename(text: str) -> str:
    """Convert text to a valid filename by removing/replacing invalid characters."""
    # Replace spaces and invalid characters with underscores
    filename = re.sub(r'[^\w\s-]', '', text)
    filename = re.sub(r'[-\s]+', '_', filename)
    # Remove leading/trailing underscores
    filename = filename.strip('_')
    # Limit length
    return filename[:100] if len(filename) > 100 else filename


def parse_job_description(raw_text: str) -> Dict[str, Any]:
    """
    Parse raw job description text into structured format using LLM.
    
    Args:
        raw_text: Raw job description text pasted by user
        
    Returns:
        Dictionary containing structured job data
    """
    llm = get_llm()
    structured_llm = llm.with_structured_output(JobDescription)
    
    prompt = f"""Extract structured information from the following job description.
If a field is not mentioned or unclear, use None for optional fields or empty list for list fields.

Job Description:
{raw_text}

Extract the job title, company name, description, requirements, location, salary, employment type, posted date, benefits, and responsibilities.
"""
    
    try:
        job_data = structured_llm.invoke(prompt)
        return job_data.model_dump()
    except Exception as e:
        # Fallback: try to extract at least title and company
        raise ValueError(f"Failed to parse job description: {str(e)}")


def save_job_description(job_data: Dict[str, Any], filename: Optional[str] = None) -> str:
    """
    Save job description to data/jobs/ directory.
    
    Args:
        job_data: Dictionary containing job data (from parse_job_description or directly provided)
        filename: Optional filename (without .json). If not provided, will be generated from title and company.
        
    Returns:
        The filename (without .json extension) where the job was saved
    """
    if filename is None:
        title = job_data.get('title', 'unknown_title')
        company = job_data.get('company', 'unknown_company')
        filename = f"{sanitize_filename(title.lower())}_{sanitize_filename(company.lower())}"
    
    # Ensure filename doesn't have .json extension
    filename = filename.replace('.json', '')
    
    filepath = JOBS_DIR / f"{filename}.json"
    
    # Handle duplicate files by appending a number
    counter = 1
    original_filepath = filepath
    while filepath.exists():
        filepath = JOBS_DIR / f"{filename}_{counter}.json"
        counter += 1
    
    # Write the job data to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(job_data, f, indent=2, ensure_ascii=False)
    
    return filepath.stem

@tool
def load_job_by_title(job_title: str) -> str:
    """Load a job description by job title from the jobs directory"""
    job_files = list(JOBS_DIR.glob("*.json"))
    
    # Normalize the search title (lowercase, replace spaces/hyphens with underscores)
    normalized_search = sanitize_filename(job_title.lower())
    
    for job_file in job_files:
        try:
            with open(job_file, 'r') as f:
                job_data = json.load(f)
            
            # Check 1: Normalized filename match (matches how we generate filenames)
            normalized_filename = job_file.stem.lower()
            if normalized_search in normalized_filename or normalized_filename.startswith(normalized_search):
                return format_job_data(job_data)
            
            # Check 2: Actual title field in JSON (flexible substring matching)
            file_title = job_data.get('title', '').lower()
            search_title_lower = job_title.lower()
            
            # Remove common punctuation for comparison
            file_title_clean = re.sub(r'[^\w\s]', ' ', file_title)
            search_title_clean = re.sub(r'[^\w\s]', ' ', search_title_lower)
            
            # Check if titles match (flexible: either contains the other)
            if (search_title_clean.strip() in file_title_clean or 
                file_title_clean.strip() in search_title_clean or
                any(word in file_title_clean for word in search_title_clean.split() if len(word) > 3)):
                return format_job_data(job_data)
                
        except (json.JSONDecodeError, IOError) as e:
            continue
    
    return f"Job with title '{job_title}' not found in directory"


def format_job_data(job_data: Dict[str, Any]) -> str:
    """Format job data into a readable string."""
    requirements = job_data.get('requirements', [])
    responsibilities = job_data.get('responsibilities', [])
    
    return f"""Job: {job_data.get('title', 'Unknown')}
Company: {job_data.get('company', 'Unknown')}
Location: {job_data.get('location', 'Unknown')}
Description: {job_data.get('description', '')}
Requirements: {', '.join(requirements) if requirements else 'Not specified'}
Responsibilities: {', '.join(responsibilities) if responsibilities else 'Not specified'}
Salary: {job_data.get('salary', job_data.get('salary_range', 'Not specified'))}
Employment Type: {job_data.get('type', job_data.get('employment_type', 'Not specified'))}
Experience Level: {job_data.get('experience_level', 'Not specified')}"""

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