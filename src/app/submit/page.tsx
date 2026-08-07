"use client";

import { useState, FormEvent, ReactNode } from "react";
import Link from "next/link";

const TYPES = [
  { value: "internship", label: "INTERNSHIP" },
  { value: "full-time", label: "FULL-TIME" },
  { value: "part-time", label: "PART-TIME" },
  { value: "contract", label: "CONTRACT" },
  { value: "fellowship", label: "FELLOWSHIP" },
];

type Status = "idle" | "submitting" | "success" | "error";

export default function SubmitJob() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    setErrorMessage("");

    const form = e.currentTarget;
    const data = new FormData(form);
    const body = {
      company: data.get("company"),
      title: data.get("title"),
      description: data.get("description"),
      type: data.get("type"),
      location: data.get("location"),
      comp: data.get("comp"),
      url: data.get("url"),
      submitterEmail: data.get("submitterEmail"),
      website: data.get("website"), // honeypot
    };

    try {
      const res = await fetch("/api/submit-job", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok) {
        setErrorMessage(json.error ?? "Something went wrong.");
        setStatus("error");
        return;
      }
      setStatus("success");
      form.reset();
    } catch {
      setErrorMessage("Network error. Please try again.");
      setStatus("error");
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b-2 border-[var(--line)]">
        <div className="mx-auto max-w-[1900px] px-8 py-4 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm tracking-wide"
          >
            <span className="inline-block h-2.5 w-2.5 border-2 border-[var(--line)] bg-[var(--accent-purple)]" />
            OREGON BLOCKCHAIN GROUP
          </Link>
          <Link
            href="/"
            className="border-2 border-[var(--line)] px-4 py-1.5 text-sm font-bold hover:bg-[var(--ink)] hover:text-[var(--bg)] transition-colors"
          >
            ← BACK TO LISTINGS
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl px-8 flex-1 py-14">
        <div className="flex items-center gap-2 text-xs tracking-widest text-[var(--muted)] mb-4">
          <span className="inline-block h-2 w-2 border border-[var(--line)] bg-[var(--accent-green)]" />
          § INDEX · SUBMIT A ROLE
        </div>
        <h1 className="text-5xl sm:text-6xl font-extrabold leading-[0.95] tracking-tight mb-4">
          POST A{" "}
          <span className="inline-block bg-[var(--accent-green)] px-2 border-2 border-[var(--line)] shadow-[4px_4px_0_var(--line)]">
            ROLE
          </span>
        </h1>
        <p className="text-base leading-relaxed text-[var(--ink)]/80 mb-10">
          Hiring crypto or blockchain talent in Oregon or remote? Submit the
          role below. Every submission is reviewed before it goes live on
          the board.
        </p>

        {status === "success" ? (
          <div className="border-2 border-[var(--line)] bg-[var(--panel)] p-8">
            <div className="text-lg font-extrabold mb-2">
              SUBMITTED FOR REVIEW
            </div>
            <p className="text-sm text-[var(--ink)]/75 leading-relaxed mb-6">
              Thanks — your role has been sent to the OBG team. Once
              approved, it&apos;ll appear on the board automatically.
            </p>
            <button
              onClick={() => setStatus("idle")}
              className="border-2 border-[var(--line)] px-4 py-1.5 text-sm font-bold hover:bg-[var(--ink)] hover:text-[var(--bg)] transition-colors"
            >
              SUBMIT ANOTHER ROLE
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="border-2 border-[var(--line)] bg-[var(--panel)] divide-y-2 divide-[var(--line)]"
          >
            {/* honeypot - hidden from real users */}
            <input
              type="text"
              name="website"
              tabIndex={-1}
              autoComplete="off"
              className="hidden"
              aria-hidden="true"
            />

            <Field label="COMPANY *">
              <input
                required
                name="company"
                maxLength={120}
                placeholder="Chainlink Labs"
                className="input"
              />
            </Field>

            <Field label="JOB TITLE *">
              <input
                required
                name="title"
                maxLength={160}
                placeholder="Protocol Engineering Intern"
                className="input"
              />
            </Field>

            <Field label="DESCRIPTION *">
              <textarea
                required
                name="description"
                maxLength={800}
                rows={4}
                placeholder="1-3 sentences about the role."
                className="input resize-none"
              />
            </Field>

            <Field label="TYPE *">
              <select required name="type" defaultValue="" className="input">
                <option value="" disabled>
                  Select a type
                </option>
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="LOCATION">
              <input
                name="location"
                maxLength={120}
                placeholder="Portland, OR or Remote"
                className="input"
              />
            </Field>

            <Field label="COMPENSATION">
              <input
                name="comp"
                maxLength={120}
                placeholder="$95,000 - $130,000 or Summer term"
                className="input"
              />
            </Field>

            <Field label="APPLICATION URL *">
              <input
                required
                type="url"
                name="url"
                placeholder="https://company.com/careers/role"
                className="input"
              />
            </Field>

            <Field label="YOUR EMAIL (optional)">
              <input
                type="email"
                name="submitterEmail"
                placeholder="you@company.com"
                className="input"
              />
            </Field>

            <div className="p-6">
              {status === "error" && (
                <div className="mb-4 text-sm text-red-700">
                  {errorMessage}
                </div>
              )}
              <button
                type="submit"
                disabled={status === "submitting"}
                className="w-full border-2 border-[var(--line)] bg-[var(--ink)] text-[var(--bg)] px-4 py-3 text-sm font-bold tracking-widest hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {status === "submitting" ? "SUBMITTING…" : "SUBMIT FOR REVIEW →"}
              </button>
            </div>
          </form>
        )}
      </main>

      <footer className="border-t-2 border-[var(--line)] py-6">
        <div className="mx-auto max-w-[1900px] px-8 flex flex-wrap items-center justify-between text-xs text-[var(--muted)] tracking-wide gap-2">
          <span>OREGON BLOCKCHAIN GROUP — STUDENT-RUN, COMMUNITY-BUILT.</span>
          <span>SUBMISSIONS ARE REVIEWED BEFORE PUBLISHING.</span>
        </div>
      </footer>

      <style>{`
        .input {
          width: 100%;
          background: transparent;
          font-family: inherit;
          font-size: 0.875rem;
          outline: none;
          border-bottom: 1px dashed rgba(22, 20, 15, 0.35);
          padding-bottom: 0.5rem;
        }
        .input:focus {
          border-bottom: 1px solid var(--line);
        }
      `}</style>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="p-6">
      <label className="block text-[11px] tracking-widest text-[var(--muted)] mb-2">
        {label}
      </label>
      {children}
    </div>
  );
}
