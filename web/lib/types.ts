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
}

export interface Home {
  today_spend_paise: number;
  today_spend_display: string;
  enquiries_today: number;
  qualified_today: number;
  cpql_paise: number | null;
  cpql_display: string | null;
  campaign_status: string[];
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
