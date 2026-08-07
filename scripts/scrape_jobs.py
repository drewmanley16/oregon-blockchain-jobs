#!/usr/bin/env python3
"""Refresh public/jobs.json from public job boards every six hours."""
from __future__ import annotations

import argparse, colorsys, hashlib, json, logging, os, re, tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public/jobs.json"
STATE = ROOT / "scripts/scraper_state.json"
HEADERS = {"User-Agent": "OregonBlockchainJobs/1.0 (+https://github.com/drewmanley16/oregon-blockchain-jobs)"}


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    method: str
    scraper: Callable[["Source"], list[dict[str, Any]]] | None
    note: str = ""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any, default: str = "") -> str:
    if value is None: return default
    return re.sub(r"\s+", " ", BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)).strip() or default


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "job"


def job_type(text: str) -> str:
    text = text.lower()
    if re.search(r"\b(intern|internship|co-op|coop)\b", text): return "internship"
    if re.search(r"\b(fellow|fellowship)\b", text): return "fellowship"
    if re.search(r"\b(part[ -]?time|temporary|temp)\b", text): return "part-time"
    if re.search(r"\b(contract|contractor|freelance|consultant)\b", text): return "contract"
    return "full-time"


def color(company: str) -> str:
    hue = int(hashlib.sha256(company.lower().encode()).hexdigest()[:6], 16) % 360
    r, g, b = colorsys.hls_to_rgb(hue / 360, .43, .62)
    return f"#{round(r*255):02x}{round(g*255):02x}{round(b*255):02x}"


def label(url: str) -> str:
    p = urlparse(url)
    return p.netloc.removeprefix("www.") + p.path.rstrip("/")


def get(url: str, **kwargs: Any) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=35, **kwargs)
    response.raise_for_status()
    return response


def normalize(raw: dict[str, Any], source: Source) -> dict[str, Any] | None:
    company, title = clean(raw.get("company")), clean(raw.get("title"))
    url = urljoin(source.url, clean(raw.get("url")))
    if not company or not title or not url.startswith(("http://", "https://")): return None
    description = clean(raw.get("description"), f"{company} is hiring a {title}.")
    sentences = re.split(r"(?<=[.!?])\s+", description)
    description = " ".join(sentences[:3])[:600]
    return {
        "id": slug(f"{company}-{title}"), "company": company,
        "companyInitial": company[0].upper(), "companyColor": color(company),
        "title": title, "description": description,
        "type": job_type(" ".join([title, clean(raw.get("employment_type")), description])),
        "featured": False, "location": clean(raw.get("location"), "Remote or unspecified"),
        "comp": clean(raw.get("comp"), "Not listed"), "url": url,
        "source": label(source.url),
    }


def json_ld(soup: BeautifulSoup, source: Source) -> list[dict[str, Any]]:
    jobs = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try: stack = [json.loads(tag.string or "null")]
        except json.JSONDecodeError: continue
        while stack:
            item = stack.pop()
            if isinstance(item, list): stack.extend(item); continue
            if not isinstance(item, dict): continue
            if item.get("@type") == "JobPosting":
                org = item.get("hiringOrganization") or {}
                loc = item.get("jobLocation") or {}
                if isinstance(loc, list): loc = loc[0] if loc else {}
                address = loc.get("address", loc) if isinstance(loc, dict) else {}
                location = ", ".join(filter(None, [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")])) if isinstance(address, dict) else clean(address)
                if item.get("jobLocationType") == "TELECOMMUTE": location = "Remote" + (f" ({location})" if location else "")
                raw = {"company": org.get("name") if isinstance(org, dict) else org, "title": item.get("title"), "description": item.get("description"), "employment_type": item.get("employmentType"), "location": location, "url": item.get("url")}
                job = normalize(raw, source)
                if job: jobs.append(job)
            stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
    return jobs


def scrape_college(source: Source) -> list[dict[str, Any]]:
    soup = BeautifulSoup(get(source.url).text, "html.parser")
    links = {urljoin(source.url, a["href"]) for a in soup.select('a[href^="/careers/"]') if re.search(r"/careers/\d+/?$", a["href"])}
    jobs = []
    for link in sorted(links):
        detail = BeautifulSoup(get(link).text, "html.parser")
        structured = json_ld(detail, source)
        if structured: jobs.extend(structured); continue
        title = clean(detail.find("h1"))
        headings = [clean(h) for h in detail.find_all(["h2", "h3"])]
        company = next((h for h in headings if h.lower() not in {"about", "about the role", "requirements", "responsibilities"}), "")
        apply = next((a.get("href") for a in detail.find_all("a", href=True) if "apply" in clean(a).lower()), link)
        job = normalize({"company": company, "title": title, "description": clean(detail), "url": apply}, source)
        if job: jobs.append(job)
    return jobs


def scrape_web3(source: Source) -> list[dict[str, Any]]:
    soup = BeautifulSoup(get(source.url).text, "html.parser")
    structured = json_ld(soup, source)
    if structured: return structured
    jobs = []
    for row in soup.select("table tr"):
        cells, links = row.find_all("td"), row.find_all("a", href=True)
        if len(cells) < 2 or not links: continue
        link = next((a for a in links if re.match(r"^/[^/]+-jobs?", a["href"])), None)
        if not link: continue
        title = clean(link); same_cell = cells[0].find_all("a")
        company = clean(same_cell[-1]) if len(same_cell) > 1 else clean(cells[0]).removeprefix(title).strip(" -")
        job = normalize({"company": company, "title": title, "location": clean(cells[2]) if len(cells)>2 else "", "comp": clean(cells[3]) if len(cells)>3 else "", "url": link["href"]}, source)
        if job: jobs.append(job)
    return jobs


def scrape_manatal(source: Source) -> list[dict[str, Any]]:
    endpoint = "https://www.careers-page.com/api/v1.0/c/techchaintalent/jobs/"
    jobs = []
    for page in range(1, 21):
        payload = get(endpoint, params={"page_size": 100, "page": page}).json()
        rows = payload.get("results", payload.get("data", []))
        if not rows: break
        for item in rows:
            raw = {"company": item.get("client_name") or item.get("company_name") or "TechChain Talent", "title": item.get("position_name") or item.get("title") or item.get("name"), "description": item.get("description") or item.get("job_description"), "employment_type": item.get("contract_type"), "location": item.get("location_display") or item.get("location"), "comp": item.get("salary_display") or item.get("salary"), "url": item.get("url") or item.get("job_url") or f"{source.url}/job/{item.get('hash', item.get('id', ''))}"}
            job = normalize(raw, source)
            if job: jobs.append(job)
        if not payload.get("next") and len(rows) < 100: break
    return jobs


def scrape_getro(source: Source) -> list[dict[str, Any]]:
    soup = BeautifulSoup(get(source.url).text, "html.parser")
    structured = json_ld(soup, source)
    if structured: return structured
    jobs, seen = [], set()
    for a in soup.select('a[href*="/companies/"][href*="/jobs/"]'):
        href = urljoin(source.url, a["href"])
        if href in seen: continue
        seen.add(href); match = re.search(r"/companies/([^/]+)/jobs/", href)
        company = match.group(1).replace("-", " ").title() if match else ""
        container = a.find_parent(["article", "li", "div"]); text = clean(container or a)
        location = re.search(r"Location:\s*(.+?)(?:Posted:|Compensation:|$)", text, re.I)
        comp = re.search(r"Compensation:\s*(.+?)(?:Posted:|$)", text, re.I)
        job = normalize({"company": company, "title": clean(a), "description": text, "location": location.group(1) if location else "", "comp": comp.group(1) if comp else "", "url": href}, source)
        if job: jobs.append(job)
    return jobs


SOURCES = [
    Source("mempool", "https://www.mempool.nyc/", "disabled", None, "Softr/Airtable company directory, not a jobs feed"),
    Source("college", "https://www.college.xyz/careers", "HTML", scrape_college),
    Source("web3-career", "https://web3.career/", "HTML", scrape_web3),
    Source("techchain", "https://www.careers-page.com/techchaintalent", "public Manatal page endpoint", scrape_manatal),
    Source("circle", "https://partners.circle.com/", "disabled", None, "Alliance partner directory, not a jobs feed"),
    Source("solana", "https://jobs.solana.com/jobs", "HTML", scrape_getro, "Getro API requires credentials"),
]


def load(path: Path, default: Any) -> Any:
    try: return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError): return default


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        try: os.unlink(temp)
        except FileNotFoundError: pass
        raise


def run(output: Path, state_path: Path, dry_run: bool) -> dict[str, Any]:
    timestamp = now(); old = load(output, {"jobs": []}); state = load(state_path, {"version": 1, "jobs": {}}); tracked = state.setdefault("jobs", {})
    managed_labels = {label(s.url) for s in SOURCES if s.scraper}
    unmanaged = [j for j in old.get("jobs", []) if j.get("source") not in managed_labels]
    success, current = set(), {}
    for source in SOURCES:
        if not source.scraper: logging.info("Skipping %s: %s", source.key, source.note); continue
        try:
            found = {j["id"]: j for j in source.scraper(source)}
            if not found: raise RuntimeError("parsed zero jobs, so this run is treated as failed")
            current[source.key] = found; success.add(source.key); logging.info("%s: %d jobs", source.key, len(found))
        except Exception as exc: logging.error("%s failed: %s", source.key, exc)
    for source in SOURCES:
        if source.key not in success: continue
        for job_id, job in current[source.key].items():
            key = f"{source.key}:{job_id}"; job["postedAt"] = tracked.get(key, {}).get("postedAt", timestamp)
            tracked[key] = {"source": source.key, "misses": 0, "postedAt": job["postedAt"], "job": job}
        for key, record in list(tracked.items()):
            if record.get("source") == source.key and key.removeprefix(f"{source.key}:") not in current[source.key]:
                record["misses"] = int(record.get("misses", 0)) + 1
                if record["misses"] >= 2: del tracked[key]
    combined = {j["id"]: j for j in unmanaged}
    for record in tracked.values():
        if record.get("job"): combined.setdefault(record["job"]["id"], record["job"])
    payload = {"updatedAt": timestamp, "jobs": sorted(combined.values(), key=lambda j: (j.get("postedAt", ""), j["id"]), reverse=True)}
    state.update({"lastRunAt": timestamp, "sourceStatus": {s.key: "ok" if s.key in success else "disabled" if not s.scraper else "failed" for s in SOURCES}})
    if not dry_run: atomic_write(output, payload); atomic_write(state_path, state)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUTPUT); parser.add_argument("--state", type=Path, default=STATE); parser.add_argument("--dry-run", action="store_true"); args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run(args.output, args.state, args.dry_run); logging.info("Output contains %d jobs%s", len(result["jobs"]), " (dry run)" if args.dry_run else "")
