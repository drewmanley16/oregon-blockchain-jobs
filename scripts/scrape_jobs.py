#!/usr/bin/env python3
"""Refresh public/jobs.json from public job boards."""
from __future__ import annotations

import argparse, colorsys, hashlib, html, json, logging, os, re, tempfile
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
    company: str = ""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any, default: str = "") -> str:
    if value is None: return default
    text = html.unescape(str(value))
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(" ", strip=True)).strip() or default


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "job"


def job_type(text: str) -> str:
    text = text.lower()
    if re.search(r"\b(intern|internship|co-op|coop)\b", text): return "internship"
    if re.search(r"\b(fellow|fellowship)\b", text): return "fellowship"
    if re.search(r"\b(part[ -]?time|temporary|temp)\b", text): return "part-time"
    if re.search(r"\b(contract|contractor|freelance|consultant)\b", text): return "contract"
    return "full-time"


# This board only serves a college blockchain club, so senior/lead/management
# postings are dropped entirely rather than just deprioritized: internships and
# fellowships are always in scope, everything else has to look explicitly
# entry-level (new grad, junior, associate, or a low years-of-experience ask).
SENIOR_PATTERN = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|head of|director|\bvp\b|vice president|"
    r"chief|executive|architect|manager|president)\b", re.I,
)
ENTRY_PATTERN = re.compile(
    r"\b(new grad(uate)?|graduate program|junior|jr\.?|associate|entry[ -]level|"
    r"early career|apprentice|campus|rotational|university (program|hire)|"
    r"co[ -]?op)\b", re.I,
)
LOW_EXPERIENCE_PATTERN = re.compile(
    r"\b(0-1|0-2|0 to 2|1-2|1 to 2 years|no prior experience|no experience required|"
    r"recent graduate|recently graduated)\b", re.I,
)


def is_entry_level(title: str, job_type_value: str, description: str = "") -> bool:
    if job_type_value in ("internship", "fellowship"):
        return True
    if SENIOR_PATTERN.search(title):
        return False
    if ENTRY_PATTERN.search(title):
        return True
    return bool(LOW_EXPERIENCE_PATTERN.search(description))


CATEGORY_RULES: list[tuple[str, str]] = [
    ("engineering", r"\b(engineer|developer|swe|software|backend|front[ -]?end|full[ -]?stack|devops|sre|infrastructure|protocol|smart contract|blockchain engineer|data engineer|ml engineer|machine learning engineer|security engineer|qa engineer|platform engineer|systems engineer)\b"),
    ("design", r"\b(designer|ux|ui|product design|brand design|design system)\b"),
    ("product", r"\b(product manager|product owner|product lead|\bpm\b|product analyst)\b"),
    ("research", r"\b(research(er)?|economist|data scientist|data science|tokenomics)\b"),
    ("community-devrel", r"\b(developer relations|devrel|dev rel|developer advocate|community|evangelist|advocate|ecosystem)\b"),
    ("marketing", r"\b(marketing|growth|content|social media|seo|comms|communications|brand)\b"),
    ("sales-partnerships", r"\b(sales|partnership|business development|\bbd\b|account executive|account manager|solutions engineer)\b"),
    ("finance-legal", r"\b(finance|accounting|accountant|legal|counsel|compliance|tax|treasury|controller|audit)\b"),
    ("operations", r"\b(operations|\bops\b|people ops|human resources|\bhr\b|recruiter|recruiting|talent|office manager|executive assistant|chief of staff)\b"),
]


def role_category(text: str) -> str:
    text = text.lower()
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text):
            return category
    return "other"


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
    department = clean(raw.get("department"))
    signal = " ".join([title, clean(raw.get("employment_type")), department, description])
    job_type_value = job_type(signal)
    if not is_entry_level(title, job_type_value, description):
        return None
    return {
        "id": slug(f"{company}-{title}"), "company": company,
        "companyInitial": company[0].upper(), "companyColor": color(company),
        "title": title, "description": description,
        "type": job_type_value, "category": role_category(" ".join([title, department])),
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
    jobs = []
    flight = ""
    for script in soup.find_all("script"):
        match = re.search(r"self\.__next_f\.push\((.*)\)$", script.string or "", re.S)
        if not match: continue
        try:
            chunk = json.loads(match.group(1))
            if len(chunk) > 1 and isinstance(chunk[1], str): flight += chunk[1]
        except json.JSONDecodeError: continue
    start = flight.find('[{"id":')
    records = json.JSONDecoder().raw_decode(flight[start:])[0] if start >= 0 else []
    for item in records:
        if item.get("status") != "active": continue
        company = (item.get("company") or {}).get("name")
        description = item.get("description") or (item.get("metadata") or {}).get("descriptionLong")
        job = normalize({"company": company, "title": item.get("name"), "description": description, "employment_type": item.get("role_type"), "location": item.get("location"), "comp": item.get("stipend"), "url": item.get("apply_link") or f"{source.url}/{item['id']}"}, source)
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
        link = next((a for a in links if re.match(r"^/[^/]+/\d+/?$", a["href"])), None)
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


def scrape_greenhouse(source: Source) -> list[dict[str, Any]]:
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{source.key}/jobs", params={"content": "true"}).json()
    jobs = []
    for item in data.get("jobs", []):
        department = ", ".join(d["name"] for d in item.get("departments", []) if d.get("name"))
        raw = {
            "company": item.get("company_name") or source.company, "title": item.get("title"),
            "description": item.get("content"), "department": department,
            "location": (item.get("location") or {}).get("name"), "url": item.get("absolute_url"),
        }
        job = normalize(raw, source)
        if job: jobs.append(job)
    return jobs


def scrape_lever(source: Source) -> list[dict[str, Any]]:
    data = get(f"https://api.lever.co/v0/postings/{source.key}", params={"mode": "json"}).json()
    jobs = []
    for item in data:
        cats = item.get("categories", {}) or {}
        raw = {
            "company": source.company, "title": item.get("text"),
            "description": item.get("descriptionPlain") or item.get("description"),
            "employment_type": cats.get("commitment"), "department": cats.get("team") or cats.get("department"),
            "location": cats.get("location"), "url": item.get("hostedUrl") or item.get("applyUrl"),
        }
        job = normalize(raw, source)
        if job: jobs.append(job)
    return jobs


def scrape_ashby(source: Source) -> list[dict[str, Any]]:
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{source.key}").json()
    jobs = []
    for item in data.get("jobs", []):
        raw = {
            "company": source.company, "title": item.get("title"),
            "description": item.get("descriptionPlain") or item.get("descriptionHtml"),
            "employment_type": item.get("employmentType"), "department": item.get("department") or item.get("team"),
            "location": item.get("location"), "url": item.get("jobUrl") or item.get("applyUrl"),
        }
        job = normalize(raw, source)
        if job: jobs.append(job)
    return jobs


SOURCES = [
    Source("mempool", "https://www.mempool.nyc/", "disabled", None, "Softr/Airtable company directory, not a jobs feed"),
    Source("college", "https://www.college.xyz/careers", "HTML", scrape_college),
    Source("web3-career", "https://web3.career/", "HTML", scrape_web3),
    Source("techchain", "https://www.careers-page.com/techchaintalent", "public Manatal page endpoint", scrape_manatal),
    Source("circle", "https://partners.circle.com/", "disabled", None, "Alliance partner directory, not a jobs feed"),
    Source("solana", "https://jobs.solana.com/jobs", "HTML", scrape_getro, "Getro API requires credentials"),

    # Greenhouse-hosted company career boards (public JSON API)
    Source("coinbase", "https://www.coinbase.com/careers", "Greenhouse API", scrape_greenhouse, company="Coinbase"),
    Source("consensys", "https://consensys.io/careers", "Greenhouse API", scrape_greenhouse, company="Consensys"),
    Source("gemini", "https://www.gemini.com/careers", "Greenhouse API", scrape_greenhouse, company="Gemini"),
    Source("paradigm", "https://www.paradigm.xyz/careers", "Greenhouse API", scrape_greenhouse, company="Paradigm"),
    Source("messari", "https://messari.io/careers", "Greenhouse API", scrape_greenhouse, company="Messari"),
    Source("bitgo", "https://www.bitgo.com/careers", "Greenhouse API", scrape_greenhouse, company="BitGo"),
    Source("ripple", "https://ripple.com/careers", "Greenhouse API", scrape_greenhouse, company="Ripple"),
    Source("zora", "https://zora.co/careers", "Greenhouse API", scrape_greenhouse, company="Zora"),
    Source("aptoslabs", "https://aptoslabs.com/careers", "Greenhouse API", scrape_greenhouse, company="Aptos Labs"),
    Source("jumpcrypto", "https://jumpcrypto.com/careers", "Greenhouse API", scrape_greenhouse, company="Jump Crypto"),

    # Lever-hosted company career boards (public JSON API)
    Source("kraken", "https://www.kraken.com/careers", "Lever API", scrape_lever, company="Kraken"),
    Source("anchorage", "https://anchorage.com/careers", "Lever API", scrape_lever, company="Anchorage Digital"),
    Source("offchainlabs", "https://offchainlabs.com/careers", "Lever API", scrape_lever, company="Offchain Labs (Arbitrum)"),
    Source("celestia", "https://celestia.org/careers", "Lever API", scrape_lever, company="Celestia Labs"),
    Source("ledger", "https://www.ledger.com/careers", "Lever API", scrape_lever, company="Ledger"),
    Source("immutable", "https://www.immutable.com/careers", "Lever API", scrape_lever, company="Immutable"),
    Source("1inch", "https://1inch.io/careers", "Lever API", scrape_lever, company="1inch"),

    # Ashby-hosted company career boards (public JSON API)
    Source("alchemy", "https://www.alchemy.com/careers", "Ashby API", scrape_ashby, company="Alchemy"),
    Source("opensea", "https://opensea.io/careers", "Ashby API", scrape_ashby, company="OpenSea"),
    Source("parity", "https://www.parity.io/careers", "Ashby API", scrape_ashby, company="Parity Technologies"),
    Source("stellar", "https://www.stellar.org/careers", "Ashby API", scrape_ashby, company="Stellar Development Foundation"),
    Source("lens", "https://lens.xyz/careers", "Ashby API", scrape_ashby, company="Lens Protocol"),
    Source("compound", "https://compound.finance/careers", "Ashby API", scrape_ashby, company="Compound Labs"),
    Source("mystenlabs", "https://sui.io/careers", "Ashby API", scrape_ashby, company="Mysten Labs (Sui)"),
    Source("magiceden", "https://magiceden.io/careers", "Ashby API", scrape_ashby, company="Magic Eden"),
    Source("skyecosystem", "https://sky.money/careers", "Ashby API", scrape_ashby, company="Sky (fka MakerDAO)"),
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
