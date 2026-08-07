# Job scraper

The `Refresh job listings` GitHub Actions workflow runs every six hours and commits changes to `public/jobs.json` and `scripts/scraper_state.json`. Vercel deploys the resulting commit.

## Source classification

| Source | Method | Notes |
| --- | --- | --- |
| College.xyz | HTML | Public server-rendered careers pages. |
| Web3.career | HTML | Public server-rendered job table. |
| TechChain Talent | Public Manatal page endpoint | Manatal's account API requires customer credentials. Its public career page uses a read-only endpoint. |
| Solana jobs | HTML | Powered by Getro. Getro's API requires credentials, so the public server-rendered board is used. |
| Mempool.NYC | Disabled | Softr/Airtable company directory, not a public job board or feed. |
| Circle Alliance Directory | Disabled | Partner directory, not a job board. |

### Company career pages

Pulled directly from each company's own career board via its ATS's public
JSON API — no HTML scraping, so these are stable across redesigns.

| ATS | Companies |
| --- | --- |
| Greenhouse | Coinbase, Consensys, Gemini, Paradigm, Messari, BitGo, Ripple, Zora, Aptos Labs, Jump Crypto |
| Lever | Kraken, Anchorage Digital, Offchain Labs (Arbitrum), Celestia Labs, Ledger, Immutable, 1inch |
| Ashby | Alchemy, OpenSea, Parity Technologies, Stellar Development Foundation, Lens Protocol, Compound Labs, Mysten Labs (Sui), Magic Eden, Sky (fka MakerDAO) |

Adding another company on one of these three platforms only requires
finding its board token (usually the URL slug at
`boards.greenhouse.io/<token>`, `jobs.lever.co/<token>`, or
`jobs.ashbyhq.com/<token>`) and adding a `Source(...)` entry in
`scripts/scrape_jobs.py` — no custom parser needed. Companies on other ATS
platforms (Workday, Ashby-alternatives, custom-built boards) need a
dedicated scraper function, same as College.xyz or Web3.career.

### Role categories

Every job also gets a `category` (engineering, product, design, marketing,
sales-partnerships, operations, finance-legal, research,
community-devrel, or other), inferred from the title and department via
keyword rules in `role_category()`. This powers the site's role-type
filter, independent of the employment-type filter (internship/full-time/etc).

Failed sources do not accrue misses. A successfully scraped source must omit a listing on two consecutive runs before it is removed. Existing listings from sources outside this managed list are preserved.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-scraper.txt
python scripts/scrape_jobs.py --dry-run
python scripts/scrape_jobs.py
```

To test without touching production files:

```bash
python scripts/scrape_jobs.py --output /tmp/jobs.json --state /tmp/scraper-state.json
python -m json.tool /tmp/jobs.json >/dev/null
```

The workflow can also be started manually from GitHub's Actions tab. Under repository Settings, Actions, General, set Workflow permissions to **Read and write permissions** so the bot can commit refreshed JSON.
