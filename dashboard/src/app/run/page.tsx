"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** /run with no id → home (no recent-runs browser). */
export default function RunIndexPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return (
    <main className="flex min-h-screen items-center justify-center text-[var(--muted)]">
      Redirecting…
    </main>
  );
}
