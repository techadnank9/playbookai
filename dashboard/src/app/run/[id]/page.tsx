"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Finding, Run } from "@/lib/insforge";

async function fetchRun(runId: string): Promise<Run | null> {
  const res = await fetch(`/api/runs/${runId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function fetchFindings(runId: string): Promise<Finding[]> {
  const res = await fetch(`/api/runs/${runId}/findings`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

const PLATFORM_AGENTS: { key: string; agent: string }[] = [
  { key: "linkedin", agent: "LinkedInAgent" },
  { key: "x", agent: "XAgent" },
  { key: "instagram", agent: "InstagramAgent" },
  { key: "tiktok", agent: "TikTokAgent" },
  { key: "youtube", agent: "YouTubeAgent" },
];

type AgentState = {
  agent: string;
  status: "queued" | "running" | "done" | "failed";
  detail: string;
};

type RankedCompetitor = {
  rank: number;
  name: string;
  handle?: string;
  url?: string;
  note?: string;
  platforms?: string[];
};

function hostname(url?: string | null): string {
  if (!url) return "";
  try {
    return new URL(url.includes("://") ? url : `https://${url}`)
      .hostname.replace(/^www\./, "")
      .toLowerCase();
  } catch {
    return url.split("//").pop()?.split("/")[0]?.replace(/^www\./, "").toLowerCase() || "";
  }
}

function brandRoots(companyName?: string | null, targetUrl?: string | null): string[] {
  const roots = new Set<string>();
  const host = hostname(targetUrl);
  if (host) roots.add(host.split(".")[0]);
  const drop = new Set([
    "group",
    "holding",
    "holdings",
    "inc",
    "llc",
    "ltd",
    "corp",
    "corporation",
    "company",
    "co",
    "nv",
    "n",
    "v",
    "ai",
    "labs",
    "the",
  ]);
  const tokens = (companyName || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  const core = tokens.filter((t) => !drop.has(t) && t.length >= 3);
  if (core[0]) roots.add(core[0]);
  return [...roots].filter((r) => r.length >= 3);
}

function normName(name: string): string {
  let n = name.trim().toLowerCase();
  const suffixes = [
    " n.v.",
    " n.v",
    " nv",
    " inc",
    " inc.",
    " llc",
    " ltd",
    " ltd.",
    " plc",
    " corp",
    " corporation",
    " holdings",
    " group",
    " company",
    " co",
    " ai",
    " labs",
  ];
  let changed = true;
  while (changed) {
    changed = false;
    for (const suffix of suffixes) {
      if (n.endsWith(suffix) && n.length > suffix.length + 1) {
        n = n.slice(0, -suffix.length).trim();
        changed = true;
        break;
      }
    }
  }
  return n.replace(/\s+/g, " ");
}

function isSelfCompetitor(
  row: { name?: string; handle?: string; url?: string },
  companyName?: string | null,
  targetUrl?: string | null
): boolean {
  const name = (row.name || "").trim().toLowerCase();
  const handle = (row.handle || "").trim().toLowerCase().replace(/^@/, "");
  const url = (row.url || "").trim().toLowerCase();
  const nameTokens = name.replace(/[^a-z0-9]+/g, " ").split(/\s+/).filter(Boolean);
  const handleAlnum = handle.replace(/[^a-z0-9]/g, "");
  const roots = brandRoots(companyName, targetUrl);
  const brand = (companyName || "").trim().toLowerCase();

  if (brand && (name === brand || name.startsWith(brand + " ") || brand.startsWith(name + " "))) {
    return true;
  }
  for (const root of roots) {
    if (nameTokens[0] === root || nameTokens.includes(root)) return true;
    if (handleAlnum === root || handleAlnum.startsWith(root)) return true;
    if (handle === root || handle.startsWith(root + "-") || handle.startsWith(root + ".")) {
      return true;
    }
    // Own LinkedIn company page only — not articles that mention the brand in the URL.
    const li = url.indexOf("linkedin.com/company/");
    if (li >= 0) {
      const slug = url
        .slice(li + "linkedin.com/company/".length)
        .split("?")[0]
        .replace(/^\/+|\/+$/g, "")
        .split("/")[0]
        .replace(/[^a-z0-9]/g, "");
      if (slug === root || slug.startsWith(root)) return true;
    }
  }
  const targetHost = hostname(targetUrl);
  const compHost = hostname(row.url);
  if (targetHost && compHost) {
    if (compHost === targetHost || compHost.endsWith("." + targetHost)) return true;
  }
  return false;
}

function topCompetitors(
  findings: Finding[],
  companyName?: string | null,
  targetUrl?: string | null
): RankedCompetitor[] {
  type Bucket = {
    name: string;
    handle: string;
    url: string;
    note: string;
    platforms: Set<string>;
    score: number;
  };
  const buckets = new Map<string, Bucket>();

  const ingest = (
    row: { name?: string; handle?: string; url?: string; note?: string },
    platforms: string[] = [],
    scoreBoost = 0
  ) => {
    const name = String(row.name || "").trim();
    if (!name) return;
    if (isSelfCompetitor(row, companyName, targetUrl)) return;
    const key = normName(name);
    if (!key) return;
    const cur = buckets.get(key);
    if (cur) {
      for (const p of platforms) if (p) cur.platforms.add(p);
      const note = String(row.note || "");
      if (note.length > cur.note.length) cur.note = note;
      if (!cur.url && row.url) cur.url = String(row.url);
      if (!cur.handle && row.handle) cur.handle = String(row.handle);
      cur.score = Math.max(cur.score, scoreBoost) + cur.platforms.size * 10;
    } else {
      buckets.set(key, {
        name,
        handle: String(row.handle || ""),
        url: String(row.url || ""),
        note: String(row.note || ""),
        platforms: new Set(platforms.filter(Boolean)),
        score: scoreBoost + platforms.filter(Boolean).length * 10,
      });
    }
  };

  const ranked = findings.find((f) => f.kind === "top_competitors");
  const fromRank = ranked?.data?.competitors;
  if (Array.isArray(fromRank) && fromRank.length) {
    for (const c of fromRank) {
      const row = c as Record<string, unknown>;
      ingest(
        {
          name: String(row.name || ""),
          handle: row.handle ? String(row.handle) : "",
          url: row.url ? String(row.url) : "",
          note: row.note ? String(row.note) : "",
        },
        Array.isArray(row.platforms) ? row.platforms.map(String) : [],
        50
      );
    }
  }

  for (const f of findings) {
    if (f.kind !== "competitor") continue;
    ingest(
      {
        name: String(f.data.name || ""),
        handle: String(f.data.handle || ""),
        url: String(f.data.url || ""),
        note: String(f.data.note || ""),
      },
      f.platform ? [f.platform] : []
    );
  }

  return Array.from(buckets.values())
    .sort(
      (a, b) =>
        b.platforms.size - a.platforms.size ||
        b.score - a.score ||
        b.note.length - a.note.length ||
        a.name.localeCompare(b.name)
    )
    .slice(0, 5)
    .map((c, i) => ({
      rank: i + 1,
      name: c.name,
      handle: c.handle || undefined,
      url: c.url || undefined,
      note: c.note || undefined,
      platforms: Array.from(c.platforms),
    }));
}

function deriveAgents(findings: Finding[], runStatus: string | null): AgentState[] {
  // Prefer explicit realtime activity events when present.
  const activityOrder: string[] = [];
  const fromActivity = new Map<string, AgentState>();
  for (const f of findings) {
    if (f.kind !== "activity") continue;
    if (!activityOrder.includes(f.agent)) activityOrder.push(f.agent);
    const status = String(f.data.status || "queued");
    fromActivity.set(f.agent, {
      agent: f.agent,
      status: (["queued", "running", "done", "failed"].includes(status)
        ? status
        : "queued") as AgentState["status"],
      detail: String(f.data.detail || ""),
    });
  }
  if (fromActivity.size > 0) {
    return activityOrder.map((name) => fromActivity.get(name)!);
  }

  // Fallback: infer live status from findings (older runs / mid-flight).
  const hasScoutProfile = findings.some(
    (f) => f.agent === "Scout" && f.kind === "profile" && !f.platform
  );
  const recruited = new Set(
    findings
      .filter((f) => f.agent === "Scout" && f.kind === "profile" && f.platform)
      .map((f) => f.platform as string)
  );
  const playbookAgents = new Set(
    findings
      .filter((f) => f.kind === "playbook" && f.agent !== "Strategist")
      .map((f) => f.agent)
  );
  const hasStrategist = findings.some(
    (f) => f.agent === "Strategist" && f.kind === "playbook"
  );
  const outreachCount = findings.filter((f) => f.kind === "outreach").length;
  const failed = runStatus === "failed";
  const complete = runStatus === "complete";

  const agents: AgentState[] = [];

  if (!hasScoutProfile) {
    agents.push({
      agent: "Scout",
      status: failed ? "failed" : "running",
      detail: failed ? "Run failed while profiling" : "Extracting site + naming company/niche",
    });
  } else {
    agents.push({
      agent: "Scout",
      status: "done",
      detail:
        recruited.size > 0
          ? `Recruited ${recruited.size} platform specialists`
          : "Company profiled",
    });
  }

  for (const { key, agent } of PLATFORM_AGENTS) {
    if (playbookAgents.has(agent)) {
      const comps = findings.filter(
        (f) => f.kind === "competitor" && f.platform === key
      ).length;
      agents.push({
        agent,
        status: "done",
        detail: `Playbook ready (${comps} competitors)`,
      });
      continue;
    }
    if (!hasScoutProfile) {
      agents.push({
        agent,
        status: "queued",
        detail: "Waiting for Scout to recruit",
      });
      continue;
    }
    if (recruited.size > 0 && !recruited.has(key)) {
      agents.push({
        agent,
        status: "done",
        detail: "Not recruited for this run",
      });
      continue;
    }
    // Scout done, this platform not finished yet → either running or queued behind others.
    const prior = PLATFORM_AGENTS.find(
      (p) => !playbookAgents.has(p.agent) && (recruited.size === 0 || recruited.has(p.key))
    );
    const isCurrent = prior?.agent === agent;
    agents.push({
      agent,
      status: failed ? "failed" : isCurrent ? "running" : "queued",
      detail: failed
        ? "Stopped"
        : isCurrent
          ? "Searching competitors + synthesizing playbook"
          : "Waiting for prior platform agents",
    });
  }

  const platformsDone =
    PLATFORM_AGENTS.filter((p) => playbookAgents.has(p.agent)).length ===
      (recruited.size || PLATFORM_AGENTS.length) ||
    playbookAgents.size >= 5;

  if (hasStrategist) {
    agents.push({
      agent: "Strategist",
      status: "done",
      detail: "Cross-platform opportunity locked",
    });
  } else {
    agents.push({
      agent: "Strategist",
      status: failed
        ? "failed"
        : platformsDone || playbookAgents.size > 0
          ? playbookAgents.size >= (recruited.size || 1)
            ? "running"
            : "queued"
          : "queued",
      detail:
        playbookAgents.size === 0
          ? "Waiting for platform playbooks"
          : "Converging platform playbooks",
    });
  }

  if (outreachCount > 0 || complete) {
    agents.push({
      agent: "Outreach",
      status: complete || outreachCount > 0 ? "done" : "running",
      detail:
        outreachCount > 0
          ? `Drafted ${outreachCount} outreach messages`
          : "Finding people + drafting messages",
    });
  } else {
    agents.push({
      agent: "Outreach",
      status: failed ? "failed" : hasStrategist ? "running" : "queued",
      detail: hasStrategist
        ? "Finding creators + drafting messages"
        : "Waiting for Strategist convergence",
    });
  }

  return agents;
}

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const runId = typeof params?.id === "string" ? params.id : "";

  const [run, setRun] = useState<Run | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    const tick = async () => {
      try {
        const [nextRun, nextFindings] = await Promise.all([
          fetchRun(runId),
          fetchFindings(runId),
        ]);
        if (!alive) return;
        setRun(nextRun);
        setFindings(nextFindings);
        setError(null);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load run");
      }
    };
    tick();
    const id = setInterval(tick, 1500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [runId]);

  const platforms = useMemo(
    () =>
      Array.from(
        new Set(
          findings
            .filter((f) => f.kind === "profile" && f.platform)
            .map((f) => f.platform as string)
        )
      ),
    [findings]
  );
  const playbooks = findings.filter(
    (f) => f.kind === "playbook" && f.agent !== "Strategist"
  );
  const convergence = findings.find(
    (f) => f.agent === "Strategist" && f.kind === "playbook"
  );
  const outreach = findings.filter((f) => f.kind === "outreach");
  const competitors = useMemo(
    () => topCompetitors(findings, run?.company_name, run?.target_url),
    [findings, run?.company_name, run?.target_url]
  );
  const agents = useMemo(
    () => deriveAgents(findings, run?.status ?? null),
    [findings, run?.status]
  );
  const runningCount = agents.filter((a) => a.status === "running").length;
  const doneCount = agents.filter((a) => a.status === "done").length;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-5 py-10 md:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--line)] pb-6">
        <div>
          <Link
            href="/"
            className="font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.24em] text-[var(--moss)] hover:underline"
          >
            ← Playbook AI
          </Link>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl text-[var(--moss-deep)] md:text-4xl">
            {run?.company_name || "Building playbook…"}
          </h1>
        </div>
        <Link
          href="/"
          className="bg-[var(--moss-deep)] px-5 py-2.5 font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-[0.18em] text-[var(--panel)]"
        >
          New URL
        </Link>
      </header>

      {error && (
        <p className="text-sm text-[var(--amber)]" role="alert">
          {error}
        </p>
      )}

      {!run ? (
        <p className="text-[var(--muted)]">Loading live run…</p>
      ) : (
        <div className="flex flex-col gap-8">
          <div>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <p className="text-sm text-[var(--muted)]">
                {run.niche || "Niche pending"} ·{" "}
                <a
                  href={run.target_url}
                  className="underline decoration-[var(--line)] underline-offset-2"
                  target="_blank"
                  rel="noreferrer"
                >
                  {run.target_url}
                </a>
              </p>
              <StatusPill status={run.status} />
            </div>
            {convergence?.data?.biggest_opportunity ? (
              <p className="mt-5 border-l-2 border-[var(--moss)] pl-4 text-lg leading-snug">
                {String(convergence.data.biggest_opportunity)}
              </p>
            ) : null}
          </div>

          <Section
            title={`Agents · ${agents.length} · ${runningCount} live · ${doneCount} done`}
          >
            <ul className="flex flex-col border-t border-[var(--line)]">
              {agents.map((a) => (
                <li
                  key={a.agent}
                  className="flex items-start gap-3 border-b border-[var(--line)] py-3"
                >
                  <AgentDot status={a.status} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm font-semibold text-[var(--ink)]">
                        {a.agent}
                      </span>
                      <span className="font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">
                        {a.status}
                      </span>
                    </div>
                    <p className="mt-0.5 text-sm text-[var(--muted)]">{a.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Platforms">
            <div className="flex flex-wrap gap-2">
              {platforms.map((p) => (
                <span
                  key={p}
                  className="bg-[var(--moss)]/10 px-3 py-1 font-[family-name:var(--font-mono)] text-xs uppercase tracking-wider text-[var(--moss-deep)]"
                >
                  {p}
                </span>
              ))}
              {!platforms.length && <Empty>Waiting on Scout…</Empty>}
            </div>
          </Section>

          <Section title="Top competitors">
            <ol className="flex flex-col border-t border-[var(--line)]">
              {competitors.map((c) => (
                <li
                  key={c.name}
                  className="flex items-start gap-3 border-b border-[var(--line)] py-3"
                >
                  <span className="mt-0.5 w-6 shrink-0 font-[family-name:var(--font-mono)] text-xs text-[var(--muted)]">
                    {c.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold">{c.name}</div>
                    <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--muted)]">
                      {[c.handle, (c.platforms || []).join(" · ")]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                    {c.note ? (
                      <p className="mt-1 text-sm text-[var(--muted)]">{c.note}</p>
                    ) : null}
                    {c.url ? (
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 inline-block text-xs underline decoration-[var(--line)] underline-offset-2"
                      >
                        {c.url}
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
              {!competitors.length && (
                <Empty>
                  {run?.status === "complete" || run?.status === "failed"
                    ? "No rivals found for this run — try again."
                    : "Still researching…"}
                </Empty>
              )}
            </ol>
          </Section>

          <Section title="Playbooks">
            <div className="grid gap-6">
              {playbooks.map((pb) => (
                <article key={pb.id} className="border-t border-[var(--line)] pt-4">
                  <h2 className="font-[family-name:var(--font-display)] text-xl text-[var(--moss-deep)]">
                    {String(pb.data.platform || pb.platform)}
                  </h2>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Cadence: {String(pb.data.cadence || "—")}
                  </p>
                  <ul className="mt-3 list-disc pl-5 text-sm">
                    {(Array.isArray(pb.data.winning_content)
                      ? pb.data.winning_content
                      : []
                    ).map((item, i) => (
                      <li key={i}>{String(item)}</li>
                    ))}
                  </ul>
                  {pb.data.gap ? (
                    <p className="mt-3 text-sm">
                      <span className="font-semibold text-[var(--moss-deep)]">Gap · </span>
                      {String(pb.data.gap)}
                    </p>
                  ) : null}
                </article>
              ))}
              {!playbooks.length && <Empty>Synthesizing…</Empty>}
            </div>
          </Section>

          <Section title="Outreach drafts">
            <div className="grid gap-5">
              {outreach.map((o) => (
                <article key={o.id} className="border-t border-[var(--line)] pt-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="text-base font-semibold">
                      {String(o.data.name || "Contact")}{" "}
                      <span className="font-[family-name:var(--font-mono)] text-xs font-normal text-[var(--muted)]">
                        {String(o.data.handle || "")}
                      </span>
                    </h2>
                    <span className="font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-wider text-[var(--muted)]">
                      {o.platform} · {String(o.data.best_channel || "")}
                    </span>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">
                    {String(o.data.draft || "")}
                  </p>
                </article>
              ))}
              {!outreach.length && <Empty>Drafting next…</Empty>}
            </div>
          </Section>
        </div>
      )}
    </main>
  );
}

function AgentDot({ status }: { status: string }) {
  const color =
    status === "running"
      ? "bg-[var(--moss)] animate-pulse"
      : status === "done"
        ? "bg-[var(--moss-deep)]"
        : status === "failed"
          ? "bg-[var(--amber)]"
          : "bg-[var(--line)]";
  return (
    <span
      className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${color}`}
      aria-hidden
    />
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
        {title}
      </h2>
      {children}
    </section>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "complete"
      ? "bg-[var(--moss)]/15 text-[var(--moss-deep)]"
      : status === "failed"
        ? "bg-[var(--amber)]/15 text-[var(--amber)]"
        : "bg-[#c9b458]/20 text-[#6b5a12]";
  return (
    <span
      className={`px-3 py-1 font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-[0.16em] ${tone}`}
    >
      {status}
    </span>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-[var(--muted)]">{children}</p>;
}
