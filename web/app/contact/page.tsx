import type { Metadata } from "next";
import { COMPANY } from "@/lib/company";
import { LegalShell } from "@/components/public";

export const metadata: Metadata = {
  title: "Contact Us — Salmor",
  description: "How to reach the Salmor team for support, billing and privacy requests.",
};

const UPDATED = "24 July 2026";

export default function Contact() {
  return (
    <LegalShell title="Contact Us" updated={UPDATED}>
      <p>
        We answer every message — in English, हिन्दी or ਪੰਜਾਬੀ. For the fastest help, write from your
        registered mobile number or email and tell us your business name.
      </p>

      <h2>Support</h2>
      <ul>
        <li>
          Email: <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a>
        </li>
        <li>Hours: {COMPANY.supportHours}</li>
        <li>We respond within 1 business day.</li>
      </ul>

      <h2>Billing & refunds</h2>
      <p>
        For payment issues include the payment reference ID from your invoice or bank statement. See our{" "}
        <a href="/refunds">Refunds & Cancellation Policy</a>.
      </p>

      <h2>Privacy & data requests</h2>
      <p>
        For access, correction, deletion or consent-withdrawal requests under the DPDP Act, see our{" "}
        <a href="/privacy">Privacy Policy</a>. Grievance Officer: {COMPANY.grievanceOfficer} —{" "}
        <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a>.
      </p>

      <h2>Business details</h2>
      <ul>
        <li>Operating name: {COMPANY.name}</li>
        <li>Legal name: {COMPANY.legalName}</li>
        <li>Country of operation: {COMPANY.country}</li>
        {COMPANY.address ? <li>Registered address: {COMPANY.address}</li> : null}
      </ul>
    </LegalShell>
  );
}
