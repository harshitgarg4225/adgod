"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { CreativeItem } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  Badge,
  Button,
  Card,
  Celebration,
  ErrorState,
  Icon,
  Loading,
  TopBar,
  useToast,
} from "@/components/ui";

export default function CreativesPage() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [creatives, setCreatives] = useState<CreativeItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [celebrate, setCelebrate] = useState(false);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      setCreatives(await api.creatives(account));
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load your ads."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function setApproval(id: string, approve: boolean) {
    try {
      if (approve) await api.approveCreative(id);
      else await api.rejectCreative(id);
      setCreatives((cs) =>
        (cs || []).map((c) =>
          c.id === id ? { ...c, approval_status: approve ? "APPROVED_FOR_LAUNCH" : "REJECTED" } : c
        )
      );
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not update."), "error");
    }
  }

  // Launch is blocked if any kept creative fails policy, or all creatives are rejected.
  const kept = (creatives || []).filter((c) => c.approval_status !== "REJECTED");
  const blocked = kept.length === 0 || kept.some((c) => c.compliance_status !== "PASSED");

  async function launch() {
    setBusy(true);
    try {
      // Launching IS approving what you kept: promote every kept, policy-passed creative
      // first — otherwise they stay DRAFT and the server rightly refuses to launch.
      const toApprove = kept.filter(
        (c) => c.compliance_status === "PASSED" && c.approval_status !== "APPROVED_FOR_LAUNCH"
      );
      await Promise.all(toApprove.map((c) => api.approveCreative(c.id)));
      await api.launch(getUser()!.account_id!);
      // The aha moment — celebrate before sending them home.
      setCelebrate(true);
      setTimeout(() => router.replace("/dashboard"), 2400);
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not launch."), "error");
      setBusy(false);
    }
  }

  if (error && !creatives) return <ErrorState message={error} onRetry={load} />;
  if (!creatives) return <Loading label={t("creatives.loading", "Saathi is designing your ads…")} />;

  return (
    <main className="min-h-[100dvh] pb-28">
      <Celebration
        show={celebrate}
        message={t("creatives.launched", "Your ads are live! Saathi is watching 24×7 🎉")}
      />
      <TopBar title={t("creatives.title", "Your ads are ready")} back="/onboarding/brief" />

      <section className="space-y-4 p-4">
        <p className="text-sm text-ink-muted">
          {t("creatives.intro", "Saathi wrote these for you. Take a look — you can change anything later.")}
        </p>
        {creatives.map((c) => {
          const ok = c.compliance_status === "PASSED";
          return (
            <Card key={c.id} className="overflow-hidden !p-0">
              <div className="relative flex aspect-[4/5] items-center justify-center bg-gradient-to-br from-brand-50 to-accent-light">
                {c.format === "VIDEO_9_16" && c.asset_url ? (
                  <>
                    <video src={c.asset_url} poster={c.thumb_url || undefined} controls className="h-full w-full object-cover" />
                    <span className="absolute left-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-2xs font-semibold text-white">
                      Video
                    </span>
                  </>
                ) : c.asset_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.asset_url} alt={c.headline || "Ad creative"} className="h-full w-full object-cover" />
                ) : (
                  <Icon name="sparkle" className="h-12 w-12 text-brand/40" />
                )}
              </div>
              <div className="space-y-1.5 p-4">
                <p className="font-semibold">{c.headline}</p>
                <p className="text-sm text-ink-muted">{c.primary_text}</p>
                <div className="flex items-center gap-2 pt-1">
                  <Badge tone={ok ? "success" : "hot"}>
                    {ok ? t("creatives.policyOk", "Policy OK") : t("creatives.needsFix", "Needs a fix")}
                  </Badge>
                  <span className="text-2xs uppercase tracking-wide text-ink-faint">{c.language}</span>
                </div>
                <div className="flex gap-2 pt-2">
                  {c.approval_status === "REJECTED" ? (
                    <Button size="sm" variant="secondary" className="flex-1" onClick={() => setApproval(c.id, true)}>
                      {t("creatives.keep", "Keep this")}
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="flex-1 !text-hot"
                      onClick={() => setApproval(c.id, false)}
                    >
                      {t("creatives.reject", "Remove")}
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </section>

      <div className="cta-dock">
        {blocked && (
          <p className="mb-2 text-center text-xs text-hot">
            {t("creatives.fixFirst", "One ad needs a fix before we can go live.")}
          </p>
        )}
        <Button fullWidth size="lg" leftIcon="play" loading={busy} disabled={blocked} onClick={launch}>
          {busy ? t("creatives.launching", "Launching…") : t("creatives.launch", "Launch my ads")}
        </Button>
      </div>
    </main>
  );
}
