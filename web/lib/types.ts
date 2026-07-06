export type Score = "HOT" | "WARM" | "COLD" | "SPAM" | null;

export interface User {
  id: string;
  name: string | null;
  role: string;
  account_id: string | null;
  locale: string;
}

export interface TokenResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface LeadListItem {
  id: string;
  name: string | null;
  intent_summary: string | null;
  score: Score;
  status: string;
  source_channel: string;
  owner_action: string;
  created_at: string;
  first_msg_at: string | null;
}

export interface Message {
  direction: "IN" | "OUT";
  type: string;
  body: string | null;
  status: string;
  created_at: string;
}

export interface LeadDetail {
  id: string;
  name: string | null;
  wa_phone: string;
  score: Score;
  status: string;
  intent_summary: string | null;
  budget_signal: string | null;
  timeline_signal: string | null;
  location_signal: string | null;
  owner_action: string;
  source_channel: string;
  created_at: string;
  qualified_at: string | null;
  transcript: Message[];
  can_message: boolean;
}

export interface Home {
  today_spend_paise: number;
  today_spend_display: string;
  enquiries_today: number;
  qualified_today: number;
  cpql_paise: number | null;
  cpql_display: string | null;
  campaign_status: string[];
  phase: string;
  autopilot_level: string;
  paused: boolean;
  daily_budget_paise: number;
  daily_budget_display: string;
  saathi_status: string;
  unread_notifications: number;
  spend_trend: number[];
}

export interface Settings {
  business_name: string;
  category: string;
  offer: string | null;
  service_area_city: string | null;
  service_radius_km: number;
  daily_budget_paise: number;
  daily_budget_display: string;
  target_cpql_paise: number;
  target_cpql_display: string;
  default_language: string;
  autopilot_level: string;
  phase: string;
  paused: boolean;
  subscription_tier: string | null;
  subscription_status: string | null;
  gstin: string | null;
  legal_name: string | null;
  billing_address: string | null;
  monthly_cap_paise: number | null;
  monthly_spend_paise: number;
  monthly_spend_display: string;
}

export interface Invoice {
  id: string;
  amount_paise: number;
  gst_paise: number;
  status: string;
  pdf_url: string | null;
  period: string | null;
}

export interface Wallet {
  balance_paise: number;
  balance_display: string;
  ledger: {
    entry_type: string;
    amount_paise: number;
    balance_paise: number;
    ref: string | null;
    created_at: string;
  }[];
}

export interface SettingsPatch {
  business_name: string;
  offer: string;
  service_area_city: string;
  service_radius_km: number;
  daily_budget_paise: number;
  target_cpql_paise: number;
  auto_approve_hours: number;
  default_language: string;
  autopilot_level: string;
  gstin: string;
  legal_name: string;
  billing_address: string;
}

export interface Booking {
  id: string;
  lead_id: string;
  lead_name: string | null;
  lead_phone: string | null;
  slot_start: string | null;
  slot_end: string | null;
  status: string;
  calendar_ref: string | null;
}

export interface Notification {
  id: string;
  kind: string;
  title: string | null;
  body: string | null;
  ref_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface BusinessInput {
  business_name: string;
  category: string;
  offer: string;
  city: string;
  radius_km: number;
  daily_budget_paise: number;
  target_cpql_paise: number;
  language: string;
}

export interface Brief {
  id?: string;
  offer?: string;
  audience?: string[];
  usp?: string[];
  objections?: string[];
  tone?: string;
  version?: number;
}

export interface Angle {
  id: string;
  title: string;
  rationale: string;
  hypothesis: string;
  status: string;
}

export interface CreativeItem {
  id: string;
  headline: string | null;
  primary_text: string | null;
  asset_url: string | null;
  thumb_url?: string | null;
  format?: string;
  compliance_status: string;
  approval_status: string;
  language: string;
}

export interface CampaignItem {
  id: string;
  status: string;
  channel: string;
  daily_budget_paise: number;
}

export interface Decision {
  action: string;
  reason_code: string | null;
  level: string;
  applied: boolean;
}

export interface Insight {
  level: string;
  spend_paise: number;
  impressions: number;
  clicks: number;
  ctr: number;
  frequency: number;
  leads: number;
  cpl_paise: number;
  cpql_paise: number;
}

export interface Tier {
  tier: string;
  price_paise: number;
  gst_paise: number;
  total_paise: number;
  price_display: string;
}

export interface SubscribeResult {
  tier: string;
  price_paise: number;
  gst_paise: number;
  total_paise: number;
  price_display: string;
  mandate_url: string;
  razorpay_subscription_id: string;
  trial_days: number;
}

export interface SubscriptionInfo {
  tier?: string;
  status: string;
  trial_end?: string | null;
  current_period_end?: string | null;
}

export interface PartnerSubAccount {
  account_id: string;
  business_name: string;
  category: string;
  phase: string;
  qualified_24h: number;
  cpql_paise: number | null;
}

export interface PartnerClientDetail {
  account_id: string;
  business_name: string;
  category: string;
  phase: string;
  city: string | null;
  daily_budget_paise: number;
  total_spend_paise: number;
  total_spend_display: string;
  total_leads: number;
  qualified_leads: number;
  cpql_paise: number | null;
  subscription_tier: string | null;
  subscription_status: string | null;
  commission_paise: number;
  commission_display: string;
}

export interface Rollup {
  accounts: number;
  live: number;
  total_spend_paise: number;
  qualified_leads: number;
  avg_cpql_paise: number | null;
}

export interface AdminAccount {
  id: string;
  tenant_id: string;
  business_name: string;
  category: string;
  phase: string;
  autopilot: string;
  trust_score: number;
}

export interface AnomalyEvent {
  id: string;
  account_id: string;
  severity: string;
  detail: Record<string, unknown>;
  action_taken: string | null;
  created_at: string;
}

export interface FeatureFlag {
  key: string;
  enabled: boolean;
  description: string | null;
}
