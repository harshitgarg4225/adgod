"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "@/lib/api";
import { SaathiAvatar } from "@/components/ui";

export default function Index() {
  const router = useRouter();
  useEffect(() => {
    const id = setTimeout(() => router.replace(getUser() ? "/dashboard" : "/login"), 350);
    return () => clearTimeout(id);
  }, [router]);
  // Branded splash so a cold start over a slow network isn't a blank white screen.
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center gap-4">
      <SaathiAvatar size={80} className="animate-pop" />
      <p className="text-2xl font-bold tracking-tight">Salmor</p>
      <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-brand border-t-transparent" />
    </main>
  );
}
