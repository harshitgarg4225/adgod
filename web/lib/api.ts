"use client";

import type {
  AdminAccount,
  AnomalyEvent,
  Angle,
  Booking,
  Brief,
  BusinessInput,
  CampaignItem,
  CreativeItem,
  Decision,
  FeatureFlag,
  Home,
  Insight,
  LeadDetail,
  LeadListItem,
  Notification,
  PartnerSubAccount,
  Rollup,
  Settings,
  SettingsPatch,
  SubscribeResult,
  SubscriptionInfo,
  Tier,
  TokenResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

const ACCESS_KEY = "salmor_access";
const USER_KEY = "salmor_user";

export function saveSession(t: TokenResponse) {
  localStorage.setItem(ACCESS_KEY, t.access);
  localStorage.setItem(USER_KEY, JSON.stringify(t.user));
}

export function clearSession() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser() {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as TokenResponse["user"]) : null;
}

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

class ApiError extends Error {
  constructor(public status: number, public userMessage: string) {
    super(userMessage);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let userMessage = "Something went wrong. Please try again in a moment.";
    try {
      const body = await res.json();
      userMessage = body.user_message || body.detail || userMessage;
    } catch {
      /* ignore */
    }
    // Centralised 401 handling: an expired/invalid session bounces to login from any
    // screen instead of stranding the user on a broken page.
    if (res.status === 401 && typeof window !== "undefined") {
      clearSession();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    throw new ApiError(res.status, userMessage);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  requestOtp: (phone: string) =>
    req<{ status: string; dev_code?: string }>("/auth/otp/request", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),
  verifyOtp: (phone: string, code: string) =>
    req<TokenResponse>("/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ phone, code }),
    }),
  home: (accountId: string) => req<Home>(`/accounts/${accountId}/home`),
  leads: (accountId: string, opts?: { q?: string; status?: string; score?: string }) => {
    const p = new URLSearchParams();
    if (opts?.q) p.set("q", opts.q);
    if (opts?.status) p.set("status", opts.status);
    if (opts?.score) p.set("score", opts.score);
    const qs = p.toString();
    return req<LeadListItem[]>(`/accounts/${accountId}/leads${qs ? `?${qs}` : ""}`);
  },
  lead: (leadId: string) => req<LeadDetail>(`/leads/${leadId}`),
  patchLead: (leadId: string, patch: { owner_action?: string; status?: string }) =>
    req<LeadDetail>(`/leads/${leadId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  sendLeadMessage: (leadId: string, text: string) =>
    req<{ message_id: string; status: string }>(`/leads/${leadId}/message`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  notifications: (accountId: string) =>
    req<Notification[]>(`/accounts/${accountId}/notifications`),
  markNotificationsRead: (accountId: string) =>
    req<{ marked: number }>(`/accounts/${accountId}/notifications/read`, { method: "POST" }),

  // Owner self-service settings + kill-switch
  settings: (accountId: string) => req<Settings>(`/accounts/${accountId}/settings`),
  updateSettings: (accountId: string, patch: Partial<SettingsPatch>) =>
    req<Settings>(`/accounts/${accountId}/settings`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  pauseAccount: (accountId: string) =>
    req<{ phase: string; paused: boolean }>(`/accounts/${accountId}/pause`, { method: "POST" }),
  resumeAccount: (accountId: string) =>
    req<{ phase: string; paused: boolean }>(`/accounts/${accountId}/resume`, { method: "POST" }),

  // Bookings
  bookings: (accountId: string) => req<Booking[]>(`/accounts/${accountId}/bookings`),
  bookLead: (leadId: string, body: { slot_start?: string; slot_end?: string }) =>
    req<Booking>(`/leads/${leadId}/book`, { method: "POST", body: JSON.stringify(body) }),
  updateBooking: (bookingId: string, status: string) =>
    req<Booking>(`/bookings/${bookingId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  // Onboarding
  setBusiness: (body: BusinessInput) =>
    req<{ account_id: string; phase: string }>("/onboarding/business", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  onboardingStatus: () =>
    req<{ phase: string; missing_steps: string[] }>("/onboarding/status"),
  connectWhatsApp: (body: {
    mode: string;
    phone?: string;
    phone_number_id?: string;
    waba_id?: string;
  }) =>
    req<{ mode: string; closer_enabled: boolean }>("/onboarding/whatsapp/connect", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  connectMeta: (body: {
    meta_business_id: string;
    ad_account_id: string;
    page_id: string;
    system_user_token?: string;
  }) =>
    req<{ status: string }>("/onboarding/meta/connect", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Saathi pipeline
  runResearch: (accountId: string) =>
    req<{ brief_id: string }>(`/accounts/${accountId}/research/run`, { method: "POST" }),
  brief: (accountId: string) => req<Brief>(`/accounts/${accountId}/brief`),
  angles: (accountId: string) => req<Angle[]>(`/accounts/${accountId}/angles`),
  generateCreatives: (accountId: string) =>
    req<{ creative_ids: string[] }>(`/accounts/${accountId}/creatives/generate`, {
      method: "POST",
    }),
  creatives: (accountId: string) =>
    req<CreativeItem[]>(`/accounts/${accountId}/creatives`),
  approveCreative: (creativeId: string) =>
    req<{ ok: boolean }>(`/creatives/${creativeId}/approve`, { method: "POST" }),
  launch: (accountId: string) =>
    req<{ campaign_ids: string[] }>(`/accounts/${accountId}/campaigns/launch`, {
      method: "POST",
    }),
  campaigns: (accountId: string) =>
    req<CampaignItem[]>(`/accounts/${accountId}/campaigns`),
  optimize: (accountId: string) =>
    req<{ decisions: Decision[] }>(`/accounts/${accountId}/optimize/run`, { method: "POST" }),
  decisions: (accountId: string) =>
    req<Decision[]>(`/accounts/${accountId}/optimization/decisions`),
  insights: (accountId: string) => req<Insight[]>(`/accounts/${accountId}/insights`),
  runReport: (accountId: string) =>
    req<{ message: string }>(`/accounts/${accountId}/report/run`, { method: "POST" }),

  // Billing
  tiers: () => req<Tier[]>("/billing/tiers"),
  subscribe: (tier: string) =>
    req<SubscribeResult>("/billing/subscribe", {
      method: "POST",
      body: JSON.stringify({ tier }),
    }),
  subscription: () => req<SubscriptionInfo>("/billing/subscription"),

  // Partner console
  partnerSubAccounts: () => req<PartnerSubAccount[]>("/partner/sub-accounts"),
  partnerRollup: () => req<Rollup>("/partner/rollup"),
  partnerCreate: (body: { business_name: string; category: string; city: string }) =>
    req<{ account_id: string }>("/partner/sub-accounts", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Admin console
  adminAccounts: (q: string) =>
    req<AdminAccount[]>(`/admin/accounts?q=${encodeURIComponent(q)}`),
  adminAnomalies: () => req<AnomalyEvent[]>("/admin/anomaly-queue"),
  adminPause: (accountId: string) =>
    req<{ phase: string }>(`/admin/accounts/${accountId}/pause`, { method: "POST" }),
  adminImpersonate: (accountId: string) =>
    req<{ access: string; impersonating: string }>(`/admin/impersonate/${accountId}`, {
      method: "POST",
    }),
  adminFlags: () => req<FeatureFlag[]>("/admin/feature-flags"),
  adminSetFlag: (key: string, enabled: boolean) =>
    req<{ key: string; enabled: boolean }>("/admin/feature-flags", {
      method: "POST",
      body: JSON.stringify({ key, enabled }),
    }),
};

export { ApiError };
