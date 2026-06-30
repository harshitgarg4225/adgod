"use client";

import type {
  Angle,
  Brief,
  BusinessInput,
  CampaignItem,
  CreativeItem,
  Decision,
  Home,
  Insight,
  LeadDetail,
  LeadListItem,
  Notification,
  SubscribeResult,
  SubscriptionInfo,
  Tier,
  TokenResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

const ACCESS_KEY = "lp_access";
const USER_KEY = "lp_user";

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
    let userMessage = "Something went wrong.";
    try {
      const body = await res.json();
      userMessage = body.user_message || body.detail || userMessage;
    } catch {
      /* ignore */
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
  leads: (accountId: string, q?: string) =>
    req<LeadListItem[]>(
      `/accounts/${accountId}/leads${q ? `?q=${encodeURIComponent(q)}` : ""}`
    ),
  lead: (leadId: string) => req<LeadDetail>(`/leads/${leadId}`),
  patchLead: (leadId: string, patch: { owner_action?: string; status?: string }) =>
    req<LeadDetail>(`/leads/${leadId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  notifications: (accountId: string) =>
    req<Notification[]>(`/accounts/${accountId}/notifications`),

  // Onboarding
  setBusiness: (body: BusinessInput) =>
    req<{ account_id: string; phase: string }>("/onboarding/business", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  onboardingStatus: () =>
    req<{ phase: string; missing_steps: string[] }>("/onboarding/status"),

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
};

export { ApiError };
