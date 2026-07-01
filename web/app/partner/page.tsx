"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, enterClient } from "@/lib/api";
import type { PartnerClientDetail, PartnerSubAccount, Rollup } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Icon,
  Input,
  Loading,
  OfflineBanner,
  Sheet,
  Stat,
  TopBar,
  useToast,
} from "@/components/ui";
import { rupees } from "@/lib/format";

export default function Partner() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [subs, setSubs] = useState<PartnerSubAccount[] | null>(null);
  const [roll, setRoll] = useState<Rollup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState<PartnerClientDetail | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, r] = await Promise.all([api.partnerSubAccounts(), api.partnerRollup()]);
      setSubs(s);
      setRoll(r);
    } catch (e: any) {
      if (e.status === 403) return router.replace("/dashboard");
      setError(e.userMessage || t("common.somethingWrong", "Could not load."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.partnerCreate({ business_name: name, category: "coaching", city: "" });
      setName("");
      await load();
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not create."), "error");
    } finally {
      setBusy(false);
    }
  }

  async function openDetail(accountId: string) {
    try {
      setDetail(await api.partnerSubAccount(accountId));
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not open client."), "error");
    }
  }

  async function openClient(accountId: string, businessName: string) {
    try {
      const r = await api.partnerOpen(accountId);
      enterClient(r.access, r.account_id, businessName);
      router.push("/dashboard");
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not open."), "error");
    }
  }

  if (error && !subs) return <ErrorState message={error} onRetry={load} />;
  if (!subs || !roll) return <Loading label={t("common.loading", "Loading…")} />;

  return (
    <main className="min-h-[100dvh] pb-10">
      <OfflineBanner />
      <TopBar title={t("partner.title", "Agency console")} back="/dashboard" />
      <section className="space-y-4 p-4">
        <div className="grid grid-cols-2 gap-2.5">
          <Stat label={t("partner.clients", "Clients")} value={`${roll.accounts} · ${roll.live} live`} />
          <Stat label={t("partner.avgCpql", "Avg CPQL")} value={rupees(roll.avg_cpql_paise)} tone="brand" />
          <Stat label={t("partner.spend", "Total spend")} value={rupees(roll.total_spend_paise)} />
          <Stat label={t("partner.qualified", "Qualified")} value={String(roll.qualified_leads)} />
        </div>

        <div className="flex gap-2">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("partner.newClient", "New client name")}
            className="flex-1"
          />
          <Button loading={busy} disabled={!name.trim()} onClick={create}>
            {t("partner.add", "Add")}
          </Button>
        </div>

        <ul className="space-y-2">
          {subs.map((s) => (
            <li key={s.account_id}>
              <button onClick={() => openDetail(s.account_id)} className="block w-full text-left">
                <Card className="flex items-center justify-between hover:shadow-elevated">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{s.business_name}</p>
                    <p className="text-xs text-ink-muted capitalize">
                      {s.category} · {s.phase.toLowerCase()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-right">
                    <div>
                      <p className="text-sm font-semibold">{rupees(s.cpql_paise)}</p>
                      <p className="text-2xs text-ink-faint">{s.qualified_24h} / 24h</p>
                    </div>
                    <Icon name="chevronRight" className="text-ink-faint" />
                  </div>
                </Card>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* Client detail sheet */}
      <Sheet open={!!detail} onClose={() => setDetail(null)} title={detail?.business_name}>
        {detail && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge tone="brand">{detail.phase.replace(/_/g, " ")}</Badge>
              {detail.subscription_tier && <Badge>{detail.subscription_tier}</Badge>}
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <Stat label={t("partner.spend", "Total spend")} value={detail.total_spend_display} />
              <Stat label={t("partner.leads", "Leads")} value={String(detail.total_leads)} />
              <Stat label={t("partner.qualified", "Qualified")} value={String(detail.qualified_leads)} tone="brand" />
              <Stat label={t("partner.commission", "Your commission")} value={detail.commission_display} tone="accent" />
            </div>
            <Button
              fullWidth
              leftIcon="home"
              onClick={() => openClient(detail.account_id, detail.business_name)}
            >
              {t("partner.openDashboard", "Open client dashboard")}
            </Button>
          </div>
        )}
      </Sheet>
    </main>
  );
}
