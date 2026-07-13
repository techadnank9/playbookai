import { listRuns } from "@/lib/insforge";
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import readline from "node:readline";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET() {
  try {
    const runs = await listRuns();
    return NextResponse.json(runs);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "unknown" },
      { status: 500 }
    );
  }
}

function normalizeUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > 500) return null;
  let candidate = trimmed;
  if (!/^https?:\/\//i.test(candidate)) {
    candidate = `https://${candidate}`;
  }
  try {
    const u = new URL(candidate);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.toString();
  } catch {
    return null;
  }
}

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as { url?: string };
    const url = normalizeUrl(body.url || "");
    if (!url) {
      return NextResponse.json(
        { error: "Enter a valid company URL (e.g. company.com)" },
        { status: 400 }
      );
    }

    const playbookRoot = path.resolve(process.cwd(), "..");
    const python = process.env.PLAYBOOK_PYTHON || "python3";
    const script = path.join(playbookRoot, "run.py");

    const child = spawn(python, ["-u", script, url], {
      cwd: playbookRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    });

    let runId: string | null = null;
    let settled = false;
    const deadline = Date.now() + 25000;

    await new Promise<void>((resolve, reject) => {
      const finish = () => {
        if (settled) return;
        settled = true;
        resolve();
      };
      const fail = (err: Error) => {
        if (settled) return;
        settled = true;
        reject(err);
      };

      const onLine = (line: string) => {
        const m = line.match(/PLAYBOOK_RUN_ID=([0-9a-f-]{36})/i);
        if (m) {
          runId = m[1];
          finish();
        }
      };

      if (child.stdout) {
        const rl = readline.createInterface({ input: child.stdout });
        rl.on("line", onLine);
      }
      if (child.stderr) {
        const rlErr = readline.createInterface({ input: child.stderr });
        rlErr.on("line", (line) => {
          onLine(line);
          console.error("[playbook]", line);
        });
      }

      child.on("error", (err) => fail(err));
      child.on("exit", (code) => {
        if (!runId) {
          fail(new Error(`Playbook AI exited before run id (code ${code})`));
        }
      });

      const timer = setInterval(() => {
        if (settled) {
          clearInterval(timer);
          return;
        }
        if (Date.now() > deadline) {
          clearInterval(timer);
          finish();
        }
      }, 250);
    });

    // Keep the agent mesh running after this request returns.
    child.unref();

    return NextResponse.json({
      ok: true,
      url,
      run_id: runId,
      message: runId
        ? "Run started — watching live findings."
        : "Run started — waiting for first InsForge write.",
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "failed to start run" },
      { status: 500 }
    );
  }
}
