"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import { useT } from "@/lib/i18n";
import {
  Badge,
  BottomNav,
  Card,
  EmptyState,
  ErrorState,
  Icon,
  Loading,
  OfflineBanner,
  TopBar,
} from "@/components/ui";

type Summary = Awaited<ReturnType<typeof api.adsSummary>>;

// "Look, this is my ad" — the proof-of-work screen. Read-only: viewing your ads must
// never re-open a launch flow.
export default function MyAdsPage() {
  const router = useRouter();
  const t = useT();
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      setData(await api.adsSummary(account));
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load your ads."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  if (error && !data) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading label={t("common.loading", "Loading…")} />;

  const reviewChip = (review: "active" | "in_review" | "rejected") =>
    review === "active" ? (
      <Badge tone="success">{t("ads.running", "Running")}</Badge>
    ) : review === "rejected" ? (
      <Badge tone="hot">{t("ads.fixing", "Being fixed")}</Badge>
    ) : (
      <Badge tone="neutral">{t("ads.inReview", "In Meta review")}</Badge>
    );

  return (
    <main className="min-h-[100dvh] pb-28">
      <OfflineBanner />
      <TopBar title={t("ads.title", "My ads")} back="/dashboard" />

      <section className="space-y-4 p-4">
        {data.campaign && (
          <Card className="flex items-center justify-between">
            <div>
              <p className="font-semibold">
                {data.campaign.destination === "call"
                  ? t("ads.callCampaign", "Call ads")
                  : t("ads.waCampaign", "WhatsApp ads")}
              </p>
              <p className="text-xs text-ink-muted">
                {data.campaign.status === "ACTIVE"
                  ? t("ads.live", "Live — {n} ad group(s) running").replace(
                      "{n}", String(data.active_adsets))
                  : t("ads.paused", "Paused")}
                {data.counts.in_review > 0 &&
                  ` · ${t("ads.someInReview", "{n} in Meta review").replace(
                    "{n}", String(data.counts.in_review))}`}
              </p>
            </div>
            <Icon
              name={data.campaign.status === "ACTIVE" ? "play" : "clock"}
              className={`h-7 w-7 ${
                data.campaign.status === "ACTIVE" ? "text-brand" : "text-ink-faint"
              }`}
            />
          </Card>
        )}

        {data.creatives.length === 0 ? (
          <EmptyState
            title={t("ads.emptyTitle", "No ads live yet")}
            hint={t("ads.emptyHint", "Once your ads launch, you'll see them here.")}
            icon="sparkle"
          />
        ) : (
          data.creatives.map((c) => (
            <Card key={c.id} className="overflow-hidden !p-0">
              <div className="relative flex aspect-[4/5] items-center justify-center bg-gradient-to-br from-brand-50 to-accent-light">
                {c.format === "VIDEO_9_16" && c.asset_url ? (
                  <video
                    src={c.asset_url}
                    poster={c.thumb_url || undefined}
                    controls
                    className="h-full w-full object-cover"
                  />
                ) : c.asset_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={c.asset_url}
                    alt={c.headline || "Ad"}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <Icon name="sparkle" className="h-12 w-12 text-brand/40" />
                )}
              </div>
              <div className="space-y-1.5 p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{c.headline}</p>
                  {reviewChip(c.review)}
                </div>
                <p className="text-sm text-ink-muted">{c.primary_text}</p>
              </div>
            </Card>
          ))
        )}
      </section>

      <BottomNav active="/dashboard" />
    </main>
  );
}
