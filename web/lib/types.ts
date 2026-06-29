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
