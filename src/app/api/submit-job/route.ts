import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const TYPES = ["internship", "full-time", "part-time", "contract", "fellowship"];
const CATEGORIES = [
  "engineering",
  "product",
  "design",
  "marketing",
  "sales-partnerships",
  "operations",
  "finance-legal",
  "research",
  "community-devrel",
  "other",
];

function badRequest(message: string) {
  return NextResponse.json({ error: message }, { status: 400 });
}

export async function POST(req: NextRequest) {
  const token = process.env.SUBMISSION_GITHUB_TOKEN;
  const repo = process.env.SUBMISSION_REPO;
  if (!token || !repo) {
    return NextResponse.json(
      { error: "Submissions are not configured yet." },
      { status: 503 }
    );
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return badRequest("Invalid request body.");
  }

  // Honeypot: real users never fill this hidden field.
  if (typeof body.website === "string" && body.website.trim() !== "") {
    return NextResponse.json({ ok: true });
  }

  const company = String(body.company ?? "").trim().slice(0, 120);
  const title = String(body.title ?? "").trim().slice(0, 160);
  const description = String(body.description ?? "").trim().slice(0, 800);
  const type = String(body.type ?? "").trim();
  const category = String(body.category ?? "").trim();
  const location = String(body.location ?? "").trim().slice(0, 120);
  const comp = String(body.comp ?? "").trim().slice(0, 120);
  const url = String(body.url ?? "").trim();
  const submitterEmail = String(body.submitterEmail ?? "").trim().slice(0, 200);

  if (!company || !title || !description || !url) {
    return badRequest("Company, title, description, and application URL are required.");
  }
  if (!TYPES.includes(type)) {
    return badRequest("Invalid job type.");
  }
  if (!CATEGORIES.includes(category)) {
    return badRequest("Invalid job category.");
  }
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
    if (!["http:", "https:"].includes(parsedUrl.protocol)) throw new Error();
  } catch {
    return badRequest("Application URL must be a valid http(s) link.");
  }

  const payload = {
    company,
    title,
    description,
    type,
    category,
    location: location || "Remote or unspecified",
    comp: comp || "Not listed",
    url: parsedUrl.toString(),
  };

  const issueTitle = `[Job Submission] ${company} — ${title}`;
  const issueBody = [
    `Submitted via the public job board form.`,
    submitterEmail ? `Submitter contact: ${submitterEmail}` : null,
    ``,
    `Label this issue \`approved\` to publish it to the site automatically.`,
    ``,
    "```json",
    JSON.stringify(payload, null, 2),
    "```",
  ]
    .filter((line) => line !== null)
    .join("\n");

  const res = await fetch(`https://api.github.com/repos/${repo}/issues`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: issueTitle,
      body: issueBody,
      labels: ["job-submission"],
    }),
  });

  if (!res.ok) {
    const detail = await res.text();
    console.error("GitHub issue creation failed", res.status, detail);
    return NextResponse.json(
      { error: "Could not submit your job right now. Please try again later." },
      { status: 502 }
    );
  }

  return NextResponse.json({ ok: true });
}
