"""
Utilities to parse raw job description text into the JSON format
used under data/jobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import hashlib
import json
import re
import unicodedata

JOBS_DIR = Path("data/jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    value = re.sub(r"_+", "_", value)
    return value.lower()[:80]


def _split_lines(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub("\u2022", "-", text)  # bullet • to dash
    lines = [re.sub("\s+", " ", ln).strip() for ln in text.split("\n")]
    return [ln for ln in lines if ln]


def _collect_section(lines: List[str], start_idx: int) -> Tuple[List[str], int]:
    items: List[str] = []
    i = start_idx
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^[A-Za-z].+:$", ln):
            break
        if re.match(r"^[-*•]\s+", ln):
            items.append(re.sub(r"^[-*•]\s+", "", ln).strip())
        else:
            if not items:
                items.append(ln)
            else:
                items[-1] = (items[-1] + " " + ln).strip()
        i += 1
    return items, i


def parse_job_text_to_dict(raw_text: str) -> Dict:
    lines = _split_lines(raw_text)

    data: Dict = {
        "title": "",
        "company": "",
        "description": "",
        "requirements": [],
        "responsibilities": [],
        "location": "",
        "salary": "",
        "type": "",
        "posted_date": "",
        "benefits": [],
        "raw_text_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    }

    # Heuristics: title/company from first 3 lines
    head = " ".join(lines[:3]) if lines else ""
    m = re.search(r"(?i)(?P<title>[A-Za-z][A-Za-z0-9 &/+-]{2,})\s+at\s+(?P<company>[A-Za-z0-9 .,&'\-]{2,})", head)
    if m:
        data["title"] = m.group("title").strip()
        data["company"] = m.group("company").strip()
    else:
        if lines:
            data["title"] = lines[0]
        if len(lines) > 1:
            data["company"] = lines[1]

    # Section parsing
    i = 0
    captured_description: List[str] = []
    while i < len(lines):
        ln = lines[i]
        low = ln.lower()
        if re.match(r"(?i)^requirements:?$", ln):
            i += 1
            items, i = _collect_section(lines, i)
            data["requirements"] = items
            continue
        if re.match(r"(?i)^(responsibilities|about the role|what you will do):?$", ln):
            i += 1
            items, i = _collect_section(lines, i)
            data["responsibilities"] = items
            continue
        if re.match(r"(?i)^benefits:?$", ln):
            i += 1
            items, i = _collect_section(lines, i)
            data["benefits"] = items
            continue
        m = re.match(r"(?i)^(location|based in):\s*(.+)$", ln)
        if m:
            data["location"] = m.group(2).strip()
            i += 1
            continue
        m = re.match(r"(?i)^(salary|compensation):\s*(.+)$", ln)
        if m:
            data["salary"] = m.group(2).strip()
            i += 1
            continue
        m = re.match(r"(?i)^(type|employment type):\s*(.+)$", ln)
        if m:
            data["type"] = m.group(2).strip()
            i += 1
            continue
        m = re.match(r"(?i)^(posted|posted date|date):\s*(.+)$", ln)
        if m:
            data["posted_date"] = m.group(2).strip()
            i += 1
            continue

        # Accumulate description until a known header appears
        if not re.match(r"^[A-Za-z].+:$", ln):
            captured_description.append(ln)
            i += 1
        else:
            i += 1

    # Description fallback
    if not data["description"]:
        desc = " ".join(captured_description).strip()
        # Trim very long lead-ins if requirements/responsibilities exist later
        data["description"] = desc[:2000]

    # Normalize empties
    for k in ["title", "company", "location", "salary", "type", "posted_date", "description"]:
        data[k] = data.get(k, "").strip()

    return data


def build_filename(job: Dict) -> str:
    title = job.get("title") or "job"
    company = job.get("company") or "company"
    base = f"{_slugify(title)}_{_slugify(company)}"
    return base or hashlib.sha1(json.dumps(job, sort_keys=True).encode()).hexdigest()[:16]


def save_job_json(job: Dict) -> Path:
    base = build_filename(job)
    path = JOBS_DIR / f"{base}.json"
    # Avoid overwriting by adding a numeric suffix
    if path.exists():
        n = 2
        while True:
            candidate = JOBS_DIR / f"{base}_{n}.json"
            if not candidate.exists():
                path = candidate
                break
            n += 1
    with path.open("w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    return path


