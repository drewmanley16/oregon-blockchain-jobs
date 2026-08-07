#!/usr/bin/env python3
"""Publish an approved job-submission issue into public/jobs.json."""
from __future__ import annotations

import colorsys
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public/jobs.json"
SOURCE_LABEL = "community submission"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "job"


def color(company: str) -> str:
    hue = int(hashlib.sha256(company.lower().encode()).hexdigest()[:6], 16) % 360
    r, g, b = colorsys.hls_to_rgb(hue / 360, 0.43, 0.62)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def extract_payload(issue_body: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", issue_body, re.S)
    if not match:
        raise ValueError("No JSON payload found in issue body.")
    return json.loads(match.group(1))


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
        raise


def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main() -> None:
    issue_body = sys.stdin.read()
    payload = extract_payload(issue_body)

    company = str(payload["company"]).strip()
    title = str(payload["title"]).strip()
    if not company or not title:
        raise ValueError("company and title are required")

    job = {
        "id": slug(f"{company}-{title}"),
        "company": company,
        "companyInitial": company[0].upper(),
        "companyColor": color(company),
        "title": title,
        "description": str(payload.get("description", "")).strip(),
        "type": payload.get("type", "full-time"),
        "featured": False,
        "location": payload.get("location") or "Remote or unspecified",
        "comp": payload.get("comp") or "Not listed",
        "url": payload["url"],
        "source": SOURCE_LABEL,
        "postedAt": now(),
    }

    data = load(OUTPUT, {"jobs": []})
    jobs = {j["id"]: j for j in data.get("jobs", [])}
    jobs[job["id"]] = job

    result = {
        "updatedAt": now(),
        "jobs": sorted(jobs.values(), key=lambda j: (j.get("postedAt", ""), j["id"]), reverse=True),
    }
    atomic_write(OUTPUT, result)
    print(f"Published {job['id']}")


if __name__ == "__main__":
    main()
