"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Notification } from "@/lib/types";
import { useT } from "@/lib/i18n";
import { EmptyState, ErrorState, Icon, Loading, OfflineBanner, TopBar } from "@/components/ui";

const KIND_ICON: Record<string, string> = {
  HOT_LEAD: "leads",
  APPROVAL: "check",
  ANOMALY: "alert",
  BILLING: "billing",
  REPORT: "reports",
  CREATIVE_READY: "sparkle",
};

// A notification that asks for action must take the owner THERE, not be inert text —
// "Your ads are ready" was previously an un-tappable list row.
const KIND_HREF: Record<string, string> = {
  CREATIVE_READY: "/onboarding/creatives",
  APPROVAL: "/onboarding/creatives",
  HOT_LEAD: "/leads",
  REPORT: "/reports",
  BILLING: "/billing",
};

export default function NotificationsPage() {
  const router = useRouter();
  const t = useT();
  const [items, setItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const user = getUser();
    if (!user?.account_id) {
      router.replace("/login");
      return;
    }
    setError(null);
    try {
      const list = await api.notifications(user.account_id);
      setItems(list);
      // Clear the unread badge once the owner has seen them.
      if (list.some((n) => !n.read_at)) {
        api.markNotificationsRead(user.account_id).catch(() => {});
      }
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load notifications."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="min-h-[100dvh] pb-10">
      <OfflineBanner />
      <TopBar title={t("notifications.title", "Notifications")} back="/dashboard" />
      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !items ? (
        <Loading label={t("common.loading", "Loading…")} />
      ) : items.length === 0 ? (
        <EmptyState
          title={t("notifications.emptyTitle", "All caught up")}
          hint={t("notifications.emptyHint", "Saathi will ping you here about hot leads and updates.")}
          icon="bell"
        />
      ) : (
        <ul className="divide-y divide-slate-100 px-4">
          {items.map((n) => (
            <li
              key={n.id}
              className={`flex gap-3 py-3.5 ${KIND_HREF[n.kind] ? "cursor-pointer active:bg-slate-50" : ""}`}
              onClick={() => KIND_HREF[n.kind] && router.push(KIND_HREF[n.kind])}
            >
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                  n.read_at ? "bg-slate-100 text-ink-faint" : "bg-brand-50 text-brand"
                }`}
              >
                <Icon name={KIND_ICON[n.kind] || "bell"} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{n.title || n.kind.replace(/_/g, " ")}</p>
                {n.body && <p className="text-sm text-ink-muted">{n.body}</p>}
                <p className="mt-0.5 text-2xs text-ink-faint">
                  {new Date(n.created_at).toLocaleString("en-IN", {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
              {!n.read_at && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" />}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
