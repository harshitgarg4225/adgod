"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Angle, Brief } from "@/lib/types";
import { useT } from "@/lib/i18n";
import { Button, Card, ErrorState, Loading, SaathiStatusCard, TopBar, useToast } from "@/components/ui";

export default function BriefPage() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [angles, setAngles] = useState<Angle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      const [b, a] = await Promise.all([api.brief(account), api.angles(account)]);
      setBrief(b);
      setAngles(a);
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load your brief."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function createAds() {
    setBusy(true);
    try {
      await api.generateCreatives(getUser()!.account_id!);
      router.replace("/onboarding/creatives");
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not generate ads."), "error");
      setBusy(false);
    }
  }

  if (error && !brief) return <ErrorState message={error} onRetry={load} />;
  if (!brief || !angles)
    return <Loading label={t("brief.loading", "Saathi is understanding your business…")} />;

  return (
    <main className="min-h-[100dvh] pb-28">
      <TopBar title={t("brief.title", "Here's what Saathi understood")} back="/onboarding" />
      <section className="space-y-4 p-4">
        <SaathiStatusCard
          line={t("brief.intro", "I studied your business. Here's my plan — tweak anything later.")}
        />
        <Item title={t("brief.offer", "Your offer")} value={brief.offer || "—"} />
        <Item title={t("brief.audience", "Who we'll target")} value={(brief.audience || []).join(", ") || "—"} />
        <Item title={t("brief.usp", "Why people choose you")} value={(brief.usp || []).join(", ") || "—"} />

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("brief.angles", "Ad ideas Saathi will test")} ({angles.length})
          </h2>
          <ul className="space-y-2">
            {angles.map((a) => (
              <li key={a.id}>
                <Card className="!p-3.5">
                  <p className="font-semibold">{a.title}</p>
                  <p className="text-sm text-ink-muted">{a.hypothesis}</p>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className="cta-dock">
        <Button fullWidth size="lg" leftIcon="check" loading={busy} onClick={createAds}>
          {busy ? t("brief.writing", "Writing your ads…") : t("brief.cta", "Looks good — create my ads")}
        </Button>
      </div>
    </main>
  );
}

function Item({ title, value }: { title: string; value: string }) {
  return (
    <Card className="!p-3.5">
      <p className="text-2xs font-medium uppercase tracking-wide text-ink-faint">{title}</p>
      <p className="mt-0.5 text-ink">{value}</p>
    </Card>
  );
}
