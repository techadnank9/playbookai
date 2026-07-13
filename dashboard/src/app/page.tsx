"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function Home() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onStart(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStarting(true);
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Could not start run");

      if (data.run_id) {
        router.push(`/run/${data.run_id}`);
        return;
      }
      router.push("/run");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start run");
      setStarting(false);
    }
  }

  return (
    <main className="bg-[#0f3d2c] text-[#f3eee4]">
      {/* Hero — first viewport, one composition */}
      <section className="relative isolate min-h-[100svh] overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0 -z-10"
          style={{
            background: `
              linear-gradient(115deg, rgba(15,61,44,0.94) 0%, rgba(15,61,44,0.5) 48%, rgba(20,32,26,0.2) 100%),
              url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.35'/%3E%3C/svg%3E"),
              linear-gradient(160deg, #0f3d2c 0%, #1a4d38 45%, #243028 100%)
            `,
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 top-1/4 h-[520px] w-[520px] rounded-full opacity-40 blur-3xl"
          style={{
            background: "radial-gradient(circle, #9bc4b0 0%, transparent 70%)",
            animation: "playbook-drift 16s ease-in-out infinite alternate",
          }}
        />

        <div className="mx-auto flex min-h-[100svh] w-full max-w-5xl flex-col justify-center px-6 py-16 md:px-10">
          <p
            className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.32em] text-[#b7d4c4]"
            style={{ animation: "playbook-rise 0.7s ease-out both" }}
          >
            GTM AI employee
          </p>

          <h1
            className="mt-5 font-[family-name:var(--font-display)] text-[clamp(3.4rem,11vw,7rem)] font-medium leading-[0.9] tracking-tight"
            style={{ animation: "playbook-rise 0.85s ease-out 0.06s both" }}
          >
            Playbook AI
          </h1>

          <p
            className="mt-6 max-w-lg text-lg leading-relaxed text-[#d5e2da] md:text-xl"
            style={{ animation: "playbook-rise 0.9s ease-out 0.12s both" }}
          >
            One company URL in. A per-platform action pack out — what to post,
            who to contact, drafts ready to send.
          </p>

          <UrlForm
            url={url}
            setUrl={setUrl}
            starting={starting}
            error={error}
            onStart={onStart}
            light
            inputId="company-url-hero"
          />

          <a
            href="#how"
            className="mt-20 w-fit font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-[0.24em] text-[#9bb5a8] transition hover:text-[#f3eee4]"
            style={{ animation: "playbook-rise 1.05s ease-out 0.28s both" }}
          >
            Scroll to see how ↓
          </a>
        </div>
      </section>

      {/* How it works */}
      <section
        id="how"
        className="relative border-t border-[#f3eee4]/12 bg-[#122821] px-6 py-24 md:px-10 md:py-32"
      >
        <div className="mx-auto max-w-5xl">
          <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.28em] text-[#8fb59f]">
            How it works
          </p>
          <h2 className="mt-4 max-w-2xl font-[family-name:var(--font-display)] text-4xl leading-tight md:text-5xl">
            A specialist mesh that reverse-engineers what is already winning.
          </h2>
          <ol className="mt-16 grid gap-12 md:grid-cols-3 md:gap-10">
            {[
              {
                n: "01",
                t: "Learn the company",
                d: "Scout reads the site with live Nimble extract and names the niche.",
              },
              {
                n: "02",
                t: "Study each platform",
                d: "LinkedIn, X, Instagram, TikTok, and YouTube agents pull competitor playbooks.",
              },
              {
                n: "03",
                t: "Ship the pack",
                d: "Strategist ranks the opportunity. Outreach drafts messages ready for Gmail.",
              },
            ].map((step) => (
              <li key={step.n} className="border-t border-[#f3eee4]/18 pt-6">
                <span className="font-[family-name:var(--font-mono)] text-xs tracking-[0.2em] text-[#8fb59f]">
                  {step.n}
                </span>
                <h3 className="mt-3 font-[family-name:var(--font-display)] text-2xl">
                  {step.t}
                </h3>
                <p className="mt-3 text-base leading-relaxed text-[#b7c9be]">
                  {step.d}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Output */}
      <section className="relative overflow-hidden border-t border-[#f3eee4]/12 bg-[#0c3326] px-6 py-24 md:px-10 md:py-32">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-20 bottom-0 h-80 w-80 rounded-full opacity-30 blur-3xl"
          style={{
            background: "radial-gradient(circle, #6d9a82 0%, transparent 70%)",
            animation: "playbook-drift 18s ease-in-out infinite alternate-reverse",
          }}
        />
        <div className="relative mx-auto max-w-5xl">
          <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.28em] text-[#8fb59f]">
            The output
          </p>
          <h2 className="mt-4 max-w-2xl font-[family-name:var(--font-display)] text-4xl leading-tight md:text-5xl">
            A playbook a founder would actually use.
          </h2>
          <p className="mt-5 max-w-xl text-lg text-[#b7c9be]">
            For every platform that matters: content angles, the gap to exploit,
            and people to contact — with personal outreach already drafted.
          </p>
          <ul className="mt-14 space-y-0 border-t border-[#f3eee4]/18">
            {[
              "3–5 concrete post angles + recommended cadence",
              "One specific gap competitors are winning that you are not",
              "Creator and prospect shortlists with public contact paths",
              "Ready-to-send drafts — optional Gmail send via Kylon",
            ].map((item) => (
              <li
                key={item}
                className="border-b border-[#f3eee4]/12 py-5 text-lg text-[#e4ede7] md:text-xl"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Closing CTA */}
      <section
        id="start"
        className="border-t border-[#f3eee4]/12 bg-[#0f3d2c] px-6 py-24 md:px-10 md:py-32"
      >
        <div className="mx-auto flex max-w-5xl flex-col items-start">
          <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.28em] text-[#8fb59f]">
            Start
          </p>
          <h2 className="mt-4 font-[family-name:var(--font-display)] text-4xl leading-tight md:text-6xl">
            Paste a URL.
            <br />
            Get the playbook.
          </h2>
          <UrlForm
            url={url}
            setUrl={setUrl}
            starting={starting}
            error={error}
            onStart={onStart}
            light
            inputId="company-url-footer"
          />
        </div>
      </section>

      <footer className="border-t border-[#f3eee4]/10 px-6 py-8 md:px-10">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.2em] text-[#7d9a8a]">
          <span>Playbook AI</span>
          <span>Nimble · Kylon · InsForge</span>
        </div>
      </footer>
    </main>
  );
}

function UrlForm({
  url,
  setUrl,
  starting,
  error,
  onStart,
  light,
  inputId = "company-url",
}: {
  url: string;
  setUrl: (v: string) => void;
  starting: boolean;
  error: string | null;
  onStart: (e: React.FormEvent) => void;
  light?: boolean;
  inputId?: string;
}) {
  return (
    <>
      <form
        onSubmit={onStart}
        className="mt-12 flex w-full max-w-xl flex-col gap-3 sm:flex-row sm:items-end"
        style={{ animation: "playbook-rise 1s ease-out 0.18s both" }}
      >
        <div className="min-w-0 flex-1">
          <label
            htmlFor={inputId}
            className={`mb-2 block font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.22em] ${
              light ? "text-[#9bb5a8]" : "text-[var(--muted)]"
            }`}
          >
            Company URL
          </label>
          <input
            id={inputId}
            type="text"
            inputMode="url"
            autoComplete="url"
            placeholder="company.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={starting}
            className={`w-full border-0 border-b bg-transparent px-0 py-3 text-lg outline-none ${
              light
                ? "border-[#f3eee4]/55 text-[#f3eee4] placeholder:text-[#f3eee4]/35 focus:border-[#f3eee4]"
                : "border-[var(--line)] text-[var(--ink)]"
            }`}
          />
        </div>
        <button
          type="submit"
          disabled={starting || !url.trim()}
          className="shrink-0 bg-[#f3eee4] px-8 py-3.5 font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.22em] text-[#0f3d2c] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-45"
        >
          {starting ? "Starting…" : "Build playbook"}
        </button>
      </form>
      {error && (
        <p className="mt-5 text-sm text-[#f0c4a8]" role="alert">
          {error}
        </p>
      )}
    </>
  );
}
