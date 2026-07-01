"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Wallet } from "@/lib/types";
import { useT } from "@/lib/i18n";
import { Button, Card, ErrorState, Loading, OfflineBanner, TopBar, useToast } from "@/components/ui";

const TOPUPS = [50000, 100000, 200000]; // paise: ₹500 / ₹1,000 / ₹2,000

export default function WalletPage() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const acc = getUser()?.account_id;
    if (!acc) {
      router.replace("/login");
      return;
    }
    setError(null);
    try {
      setWallet(await api.wallet());
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load wallet."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function topup(paise: number) {
    const acc = getUser()!.account_id!;
    setBusy(true);
    try {
      await api.walletTopup(paise);
      toast.show(t("wallet.added", "Added to your ad wallet."));
      await load();
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not top up."), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] pb-10">
      <OfflineBanner />
      <TopBar title={t("wallet.title", "Ad wallet")} back="/billing" />
      {error && !wallet ? (
        <ErrorState message={error} onRetry={load} />
      ) : !wallet ? (
        <Loading label={t("common.loading", "Loading…")} />
      ) : (
        <div className="space-y-4 p-4">
          <Card className="!bg-gradient-to-br !from-brand !to-brand-700 !text-white">
            <p className="text-2xs font-semibold uppercase tracking-wide text-white/70">
              {t("wallet.balance", "Balance")}
            </p>
            <p className="mt-1 text-3xl font-bold">{wallet.balance_display}</p>
          </Card>

          <div>
            <p className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
              {t("wallet.addFunds", "Add funds")}
            </p>
            <div className="grid grid-cols-3 gap-2">
              {TOPUPS.map((p) => (
                <Button key={p} variant="secondary" disabled={busy} onClick={() => topup(p)}>
                  ₹{(p / 100).toLocaleString("en-IN")}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
              {t("wallet.history", "History")}
            </p>
            {wallet.ledger.length === 0 ? (
              <Card>
                <p className="text-sm text-ink-muted">{t("wallet.noHistory", "No transactions yet.")}</p>
              </Card>
            ) : (
              <ul className="space-y-2">
                {wallet.ledger.map((l, i) => (
                  <li key={i}>
                    <Card className="flex items-center justify-between !p-3">
                      <div>
                        <p className="font-medium capitalize">{l.entry_type.toLowerCase().replace(/_/g, " ")}</p>
                        <p className="text-2xs text-ink-faint">
                          {new Date(l.created_at).toLocaleDateString("en-IN")}
                        </p>
                      </div>
                      <span className={`font-semibold ${l.amount_paise < 0 ? "text-hot" : "text-brand"}`}>
                        {l.amount_paise < 0 ? "-" : "+"}₹{Math.abs(l.amount_paise / 100).toLocaleString("en-IN")}
                      </span>
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
