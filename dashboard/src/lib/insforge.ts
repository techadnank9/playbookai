export type Run = {
  id: string;
  target_url: string;
  company_name: string | null;
  niche: string | null;
  status: string;
  created_at: string;
};

export type Finding = {
  id: string;
  run_id: string;
  agent: string;
  platform: string | null;
  kind: string;
  data: Record<string, unknown>;
  created_at: string;
};

const base = () =>
  (process.env.NEXT_PUBLIC_INSFORGE_URL || "").replace(/\/$/, "");
const key = () => process.env.NEXT_PUBLIC_INSFORGE_ANON_KEY || "";

async function records<T>(path: string): Promise<T[]> {
  const url = `${base()}/api/database/records/${path}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${key()}`,
      Prefer: "return=representation",
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`InsForge ${res.status}: ${await res.text()}`);
  }
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function listRuns(): Promise<Run[]> {
  return records<Run>("runs?order=created_at.desc&limit=20");
}

export async function getRun(id: string): Promise<Run | null> {
  const rows = await records<Run>(`runs?id=eq.${id}`);
  return rows[0] ?? null;
}

export async function listFindings(runId: string): Promise<Finding[]> {
  return records<Finding>(
    `findings?run_id=eq.${runId}&order=created_at.asc`
  );
}
