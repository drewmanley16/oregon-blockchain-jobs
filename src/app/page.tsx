"use client";

import { useEffect, useMemo, useState } from "react";

type JobType =
  | "internship"
  | "full-time"
  | "part-time"
  | "contract"
  | "fellowship";

type Job = {
  id: string;
  company: string;
  companyInitial: string;
  companyColor: string;
  title: string;
  description: string;
  type: JobType;
  featured: boolean;
  location: string;
  comp: string;
  url: string;
  source: string;
  postedAt: string;
};

type JobsFile = {
  updatedAt: string;
  jobs: Job[];
};

const FILTERS: { key: JobType | "all"; label: string }[] = [
  { key: "all", label: "ALL" },
  { key: "internship", label: "INTERNSHIP" },
  { key: "full-time", label: "FULL-TIME" },
  { key: "part-time", label: "PART-TIME" },
  { key: "contract", label: "CONTRACT" },
  { key: "fellowship", label: "FELLOWSHIP" },
];

const TYPE_LABEL: Record<JobType, string> = {
  internship: "INTERNSHIP",
  "full-time": "FULL-TIME",
  "part-time": "PART-TIME",
  contract: "CONTRACT",
  fellowship: "FELLOWSHIP",
};

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / 86_400_000);
  if (days <= 0) return "TODAY";
  if (days === 1) return "1 DAY AGO";
  if (days < 30) return `${days} DAYS AGO`;
  const months = Math.floor(days / 30);
  return `${months} MO AGO`;
}

export default function Home() {
  const [data, setData] = useState<JobsFile | null>(null);
  const [filter, setFilter] = useState<JobType | "all">("all");
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch("/jobs.json", { cache: "no-store" });
        if (!res.ok) throw new Error("bad status");
        const json: JobsFile = await res.json();
        if (!cancelled) {
          setData(json);
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    }

    load();
    const interval = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const jobs = useMemo(() => data?.jobs ?? [], [data]);

  const counts = useMemo(() => {
    const byType: Record<string, number> = { all: jobs.length };
    for (const j of jobs) byType[j.type] = (byType[j.type] ?? 0) + 1;
    return byType;
  }, [jobs]);

  const companyCount = useMemo(
    () => new Set(jobs.map((j) => j.company)).size,
    [jobs]
  );
  const featuredCount = useMemo(
    () => jobs.filter((j) => j.featured).length,
    [jobs]
  );

  const filtered = useMemo(() => {
    const list =
      filter === "all" ? jobs : jobs.filter((j) => j.type === filter);
    return [...list].sort((a, b) => {
      if (a.featured !== b.featured) return a.featured ? -1 : 1;
      return new Date(b.postedAt).getTime() - new Date(a.postedAt).getTime();
    });
  }, [jobs, filter]);

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b-2 border-[var(--line)]">
        <div className="mx-auto max-w-[1900px] px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm tracking-wide">
            <span className="inline-block h-2.5 w-2.5 border-2 border-[var(--line)] bg-[var(--accent-purple)]" />
            OREGON BLOCKCHAIN GROUP
          </div>
          <a
            href="/submit"
            className="border-2 border-[var(--line)] px-4 py-1.5 text-sm font-bold hover:bg-[var(--ink)] hover:text-[var(--bg)] transition-colors"
          >
            SUBMIT A ROLE →
          </a>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1900px] px-8 flex-1">
        <div className="pt-14 pb-10 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-10">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 text-xs tracking-widest text-[var(--muted)] mb-4">
              <span className="inline-block h-2 w-2 border border-[var(--line)] bg-[var(--accent-blue)]" />
              § INDEX · CRYPTO CAREERS
            </div>
            <h1 className="text-6xl sm:text-7xl font-extrabold leading-[0.95] tracking-tight">
              ONCHAIN{" "}
              <span className="inline-block bg-[var(--accent-purple)] px-2 border-2 border-[var(--line)] shadow-[4px_4px_0_var(--line)]">
                ROLES
              </span>
              <br />
              WORTH <span className="text-[var(--muted)]">TAKING</span>
              <span>.</span>
            </h1>
            <p className="mt-6 text-base leading-relaxed text-[var(--ink)]/80">
              Crypto and blockchain jobs across Oregon and remote —
              internships, research fellowships, and full-time offers.
              Scraped continuously from company career pages and posted
              here automatically. Apply directly, no platform in between.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-0 border-2 border-[var(--line)] shrink-0">
            <StatBox
              value={counts.all ?? 0}
              label="OPEN"
              swatch="var(--accent-blue)"
            />
            <StatBox
              value={companyCount}
              label="COMPANIES"
              swatch="var(--accent-tan)"
              borderX
            />
            <StatBox
              value={featuredCount}
              label="FEATURED"
              swatch="var(--accent-green)"
            />
          </div>
        </div>

        <div className="border-t-2 border-b-2 border-[var(--line)] py-4 flex flex-wrap items-center gap-3">
          <span className="inline-block h-2.5 w-2.5 bg-[var(--ink)]" />
          <span className="text-xs tracking-widest mr-1">FILTER</span>
          {FILTERS.map((f) => {
            const active = filter === f.key;
            const count = counts[f.key] ?? 0;
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`border-2 border-[var(--line)] px-4 py-1.5 text-xs tracking-wide font-bold transition-colors ${
                  active
                    ? "bg-[var(--ink)] text-[var(--bg)]"
                    : "bg-[var(--panel)] hover:bg-[var(--bg-dot)]"
                }`}
              >
                {f.label} · {count}
              </button>
            );
          })}
        </div>

        <div className="py-4 flex items-center justify-between text-xs text-[var(--muted)] tracking-wide">
          <span>
            {error
              ? "COULD NOT REACH jobs.json — SHOWING LAST KNOWN DATA"
              : data
              ? `LAST UPDATED ${new Date(data.updatedAt)
                  .toUTCString()
                  .slice(0, 22)} UTC`
              : "LOADING…"}
          </span>
          <span>{filtered.length} SHOWN</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-0 border-t-2 border-l-2 border-[var(--line)] mb-16">
          {filtered.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
          {data && filtered.length === 0 && (
            <div className="border-r-2 border-b-2 border-[var(--line)] p-10 col-span-full text-center text-sm text-[var(--muted)]">
              No roles match this filter right now. Check back soon — new
              postings sync automatically.
            </div>
          )}
        </div>
      </main>

      <footer className="border-t-2 border-[var(--line)] py-6">
        <div className="mx-auto max-w-[1900px] px-8 flex flex-wrap items-center justify-between text-xs text-[var(--muted)] tracking-wide gap-2">
          <span>OREGON BLOCKCHAIN GROUP — STUDENT-RUN, COMMUNITY-BUILT.</span>
          <span>POSTINGS REFRESH AUTOMATICALLY EVERY FEW HOURS.</span>
        </div>
      </footer>
    </div>
  );
}

function StatBox({
  value,
  label,
  swatch,
  borderX,
}: {
  value: number;
  label: string;
  swatch: string;
  borderX?: boolean;
}) {
  return (
    <div className={`px-6 py-4 ${borderX ? "border-x-2 border-[var(--line)]" : ""}`}>
      <div className="text-4xl font-extrabold leading-none">{value}</div>
      <div className="mt-2 flex items-center gap-1.5 text-[11px] tracking-widest text-[var(--muted)]">
        <span
          className="inline-block h-2 w-2 border border-[var(--line)]"
          style={{ background: swatch }}
        />
        {label}
      </div>
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <a
      href={job.url}
      target="_blank"
      rel="noreferrer"
      className="group border-r-2 border-b-2 border-[var(--line)] p-6 flex flex-col bg-[var(--panel)] hover:bg-white transition-colors min-h-[260px]"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span
            className="flex h-6 w-6 items-center justify-center border-2 border-[var(--line)] text-[11px] font-bold text-white"
            style={{ background: job.companyColor }}
          >
            {job.companyInitial}
          </span>
          <span className="text-xs tracking-widest text-[var(--muted)]">
            {job.company.toUpperCase()}
          </span>
        </div>
        {job.featured ? (
          <span className="border-2 border-[var(--line)] bg-[var(--accent-green)] px-2 py-0.5 text-[10px] font-bold tracking-widest">
            FEATURED
          </span>
        ) : (
          <span className="border-2 border-[var(--line)] px-2 py-0.5 text-[10px] font-bold tracking-widest">
            {TYPE_LABEL[job.type]}
          </span>
        )}
      </div>

      <h3 className="text-lg font-extrabold leading-tight tracking-tight mb-2">
        {job.title.toUpperCase()}
      </h3>
      <p className="text-sm leading-relaxed text-[var(--ink)]/75 line-clamp-3">
        {job.description}
      </p>

      <div className="mt-auto pt-4">
        <div className="border-t border-dashed border-[var(--line)]/50 mb-3" />
        <div className="flex items-center justify-between text-xs tracking-wide">
          <span className="text-[var(--muted)]">
            {job.location} · {job.comp}
          </span>
          <span className="font-bold group-hover:translate-x-0.5 transition-transform">
            →
          </span>
        </div>
        <div className="mt-1 text-[10px] text-[var(--muted)]/70 tracking-widest">
          {timeAgo(job.postedAt)} · {job.source}
        </div>
      </div>
    </a>
  );
}
