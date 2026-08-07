# Oregon Blockchain Group — Jobs

Single-page job board for crypto/blockchain roles across Oregon and remote.
Static Next.js site reading from `public/jobs.json`, kept fresh by a
scheduled scraper and a public submission form.

Live at: https://oregon-blockchain-jobs.vercel.app

## How data gets in

1. **Scraper** (`scripts/scrape_jobs.py`) — runs on a schedule via
   `.github/workflows/scrape-jobs.yml`, pulls from the sources listed in
   `SCRAPER.md`, and commits the refreshed `public/jobs.json` back to `main`.
   Vercel redeploys automatically on push.
2. **Public submissions** — the `/submit` page posts to `/api/submit-job`,
   which opens a GitHub issue labeled `job-submission` in this repo. Label
   the issue `approved` and `.github/workflows/publish-submission.yml`
   parses it and appends the job to `public/jobs.json` automatically, then
   closes the issue.

Both paths write the same `public/jobs.json` shape:

```json
{
  "updatedAt": "ISO timestamp",
  "jobs": [
    {
      "id": "unique-slug",
      "company": "...", "companyInitial": "C", "companyColor": "#hex",
      "title": "...", "description": "...",
      "type": "internship" | "full-time" | "part-time" | "contract" | "fellowship",
      "featured": false,
      "location": "...", "comp": "...",
      "url": "...", "source": "...", "postedAt": "ISO timestamp"
    }
  ]
}
```

## Setting up submissions (one-time)

The submission API needs a GitHub token with permission to open issues on
this repo:

1. Go to https://github.com/settings/personal-access-tokens/new
2. **Repository access**: "Only select repositories" → `oregon-blockchain-jobs`
3. **Permissions** → Repository permissions → **Issues: Read and write**
   (leave everything else at "No access")
4. Generate the token and copy it
5. Add it to Vercel:
   ```bash
   vercel env add SUBMISSION_GITHUB_TOKEN production
   vercel env add SUBMISSION_GITHUB_TOKEN preview
   vercel env add SUBMISSION_GITHUB_TOKEN development
   vercel --prod   # redeploy so the new env var takes effect
   ```

`SUBMISSION_REPO` is already set to `drewmanley16/oregon-blockchain-jobs`.

## Local development

```bash
npm install
npm run dev
```

Open http://localhost:3000. The `/submit` form will return a 503 locally
unless you also set `SUBMISSION_GITHUB_TOKEN` / `SUBMISSION_REPO` in
`.env.local`.

## Scraper

See `SCRAPER.md` for source classification and how to run it locally.
