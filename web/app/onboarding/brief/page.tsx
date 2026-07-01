"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Angle, Brief } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Icon,
  Loading,
  SaathiStatusCard,
  Textarea,
  TopBar,
  useToast,
} from "@/components/ui";

export default function BriefPage() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [angles, setAngles] = useState<Angle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingOffer, setEditingOffer] = useState(false);
  const [offer, setOffer] = useState("");

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      const [b, a] = await Promise.all([api.brief(account), api.angles(account)]);
      setBrief(b);
      setOffer(b.offer || "");
      setAngles(a);
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load your brief."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function saveOffer() {
    const account = getUser()!.account_id!;
    try {
      const b = await api.updateBrief(account, { offer });
      setBrief(b);
      setEditingOffer(false);
      toast.show(t("brief.saved", "Updated. Saathi will use this."));
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not save."), "error");
    }
  }

  async function toggleAngle(a: Angle) {
    const next = a.status === "PAUSED" ? "ACTIVE" : "PAUSED";
    try {
      await api.updateAngle(a.id, next);
      setAngles((xs) => (xs || []).map((x) => (x.id === a.id ? { ...x, status: next } : x)));
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not update."), "error");
    }
  }

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
        {/* Editable offer — a wrong brief poisons every ad, so let the owner fix it */}
        <Card className="!p-3.5">
          <div className="flex items-center justify-between">
            <p className="text-2xs font-medium uppercase tracking-wide text-ink-faint">
              {t("brief.offer", "Your offer")}
            </p>
            {!editingOffer && (
              <button
                onClick={() => setEditingOffer(true)}
                className="flex items-center gap-1 text-xs font-semibold text-brand"
              >
                <Icon name="edit" className="h-4 w-4" /> {t("common.edit", "Edit")}
              </button>
            )}
          </div>
          {editingOffer ? (
            <div className="mt-2 space-y-2">
              <Textarea voice rows={3} value={offer} onChange={(e) => setOffer(e.target.value)} />
              <div className="flex gap-2">
                <Button size="sm" onClick={saveOffer}>
                  {t("common.save", "Save")}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => { setEditingOffer(false); setOffer(brief.offer || ""); }}>
                  {t("common.cancel", "Cancel")}
                </Button>
              </div>
            </div>
          ) : (
            <p className="mt-0.5 text-ink">{brief.offer || "—"}</p>
          )}
        </Card>
        <Item title={t("brief.audience", "Who we'll target")} value={(brief.audience || []).join(", ") || "—"} />
        <Item title={t("brief.usp", "Why people choose you")} value={(brief.usp || []).join(", ") || "—"} />

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("brief.angles", "Ad ideas Saathi will test")} ({angles.filter((a) => a.status !== "PAUSED").length})
          </h2>
          <ul className="space-y-2">
            {angles.map((a) => {
              const paused = a.status === "PAUSED";
              return (
                <li key={a.id}>
                  <Card className={`!p-3.5 ${paused ? "opacity-60" : ""}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold">{a.title}</p>
                        <p className="text-sm text-ink-muted">{a.hypothesis}</p>
                      </div>
                      <button onClick={() => toggleAngle(a)} className="shrink-0">
                        <Badge tone={paused ? "neutral" : "brand"}>
                          {paused ? t("brief.paused", "Off") : t("brief.on", "On")}
                        </Badge>
                      </button>
                    </div>
                  </Card>
                </li>
              );
            })}
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
