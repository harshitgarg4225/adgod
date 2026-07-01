"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Booking } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Icon,
  Loading,
  OfflineBanner,
  TopBar,
  useToast,
} from "@/components/ui";

const TONE: Record<string, "brand" | "success" | "hot" | "neutral"> = {
  PROPOSED: "neutral",
  CONFIRMED: "brand",
  COMPLETED: "success",
  CANCELLED: "hot",
};

export default function BookingsPage() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [items, setItems] = useState<Booking[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const user = getUser();
    if (!user?.account_id) {
      router.replace("/login");
      return;
    }
    setError(null);
    try {
      setItems(await api.bookings(user.account_id));
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load bookings."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function setStatus(id: string, status: string) {
    try {
      await api.updateBooking(id, status);
      toast.show(t("bookings.updated", "Booking updated."));
      load();
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not update."), "error");
    }
  }

  return (
    <main className="min-h-[100dvh] pb-10">
      <OfflineBanner />
      <TopBar title={t("bookings.title", "Bookings")} back="/dashboard" />
      {error && !items ? (
        <ErrorState message={error} onRetry={load} />
      ) : !items ? (
        <Loading label={t("common.loading", "Loading…")} />
      ) : items.length === 0 ? (
        <EmptyState
          title={t("bookings.emptyTitle", "No bookings yet")}
          hint={t("bookings.emptyHint", "Book a qualified lead from their chat to fill your calendar.")}
          icon="clock"
        />
      ) : (
        <ul className="space-y-2 p-4">
          {items.map((b) => (
            <li key={b.id}>
              <Card className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <Link href={`/leads/${b.lead_id}`} className="font-semibold hover:text-brand">
                      {b.lead_name || t("leads.newEnquiry", "New enquiry")}
                    </Link>
                    <p className="text-sm text-ink-muted">
                      {b.slot_start
                        ? new Date(b.slot_start).toLocaleString("en-IN", {
                            weekday: "short",
                            day: "numeric",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : t("bookings.noTime", "Time to be confirmed")}
                    </p>
                  </div>
                  <Badge tone={TONE[b.status] || "neutral"}>{b.status}</Badge>
                </div>
                {b.status !== "CANCELLED" && b.status !== "COMPLETED" && (
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" className="flex-1" onClick={() => setStatus(b.id, "COMPLETED")}>
                      <Icon name="check" className="h-4 w-4" /> {t("bookings.done", "Done")}
                    </Button>
                    <Button size="sm" variant="secondary" className="flex-1 !text-hot" onClick={() => setStatus(b.id, "CANCELLED")}>
                      {t("bookings.cancel", "Cancel")}
                    </Button>
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
