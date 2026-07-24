/**
 * Company/legal identity — the ONE place to update when the business registers
 * formally (legal entity name, GSTIN, registered address, support address).
 * Referenced by the public landing page and every legal page.
 */
export const COMPANY = {
  name: "Salmor",
  // Update to the registered legal entity once incorporated (e.g. "Salmor Technologies Pvt Ltd").
  legalName: "Salmor",
  email: "harshitgarg4225@gmail.com",
  supportHours: "Mon–Sat, 10:00–19:00 IST",
  // DPDP grievance officer (Section 13) — the founder until a dedicated officer is named.
  grievanceOfficer: "Founder, Salmor",
  // Add the registered/operating address here once available; pages show it automatically.
  address: "",
  country: "India",
} as const;

export const PRICING = [
  { tier: "STARTER", priceInr: 1499 },
  { tier: "GROWTH", priceInr: 3499 },
  { tier: "PRO", priceInr: 6999 },
] as const;

export const TRIAL_DAYS = 7;
