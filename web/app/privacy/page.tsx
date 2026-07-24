import type { Metadata } from "next";
import { COMPANY } from "@/lib/company";
import { LegalShell } from "@/components/public";

export const metadata: Metadata = {
  title: "Privacy Policy — Salmor",
  description: "How Salmor collects, uses and protects personal data (DPDP Act, 2023).",
};

const UPDATED = "24 July 2026";

export default function Privacy() {
  return (
    <LegalShell title="Privacy Policy" updated={UPDATED}>
      <p>
        This Privacy Policy explains how {COMPANY.legalName} (&ldquo;{COMPANY.name}&rdquo;,
        &ldquo;we&rdquo;, &ldquo;us&rdquo;) collects, uses, shares and protects personal data when you use
        our platform and services (the &ldquo;Service&rdquo;). It is written to meet the requirements of
        India&rsquo;s Digital Personal Data Protection Act, 2023 (&ldquo;DPDP Act&rdquo;), under which we
        act as the <strong>data fiduciary</strong> for your account data.
      </p>

      <h2>1. Data we collect</h2>
      <h3>From you (the business owner)</h3>
      <ul>
        <li>Account data: mobile number, name, preferred language.</li>
        <li>Business data: business name, category, location/service area, offers, budgets, ad preferences.</li>
        <li>Connections you authorise: Meta ad account/Page identifiers and access tokens, WhatsApp number routing.</li>
        <li>Billing data: subscription tier, invoices, GSTIN if you provide one. Payment instruments (UPI/card) are collected and stored by Razorpay, our payment partner — we never see or store them.</li>
        <li>Technical data: device/browser type, IP address, and service logs needed for security and reliability.</li>
      </ul>
      <h3>About your leads (your customers)</h3>
      <ul>
        <li>
          Contact details and messages of people who respond to your ads (name, phone number, WhatsApp/chat
          messages, form answers). We process this <strong>on your behalf and on your instructions</strong> to
          greet, qualify and hand these enquiries to you. You are responsible for having the right to
          contact and use your leads&rsquo; information.
        </li>
      </ul>

      <h2>2. Why we use it (purposes)</h2>
      <ul>
        <li>Operating the Service: creating and running your ad campaigns, receiving and qualifying leads, showing you reports.</li>
        <li>Authentication (OTP to your mobile number) and account security.</li>
        <li>Billing, GST invoicing and fraud prevention.</li>
        <li>Service messages: OTPs, alerts you enable (e.g. hot-lead and spend alerts), daily reports.</li>
        <li>Improving reliability and safety of the Service (aggregated, minimised diagnostics).</li>
      </ul>
      <p>
        Our lawful basis is your <strong>consent</strong>, given when you sign up and use the Service, plus
        legitimate uses permitted by the DPDP Act (e.g. complying with law). We do not sell personal data,
        and we do not use your leads&rsquo; data to advertise to them for anyone else.
      </p>

      <h2>3. Who we share it with (processors)</h2>
      <p>We share data only with processors needed to run the Service, under contracts limiting their use:</p>
      <ul>
        <li><strong>Meta Platforms</strong> — to run your ads and receive your ad enquiries/lead forms.</li>
        <li><strong>WhatsApp Business providers</strong> — to send and receive WhatsApp messages on your number(s).</li>
        <li><strong>Razorpay</strong> — subscription payments, mandates and settlement.</li>
        <li><strong>AI model providers</strong> (e.g. Anthropic, Google) — to generate ad copy/images and draft lead replies. Content needed for the task (e.g. your business brief, a lead&rsquo;s message) is sent for processing; we do not permit them to use it for training under our agreements.</li>
        <li><strong>Cloud hosting and SMS providers</strong> — infrastructure, databases and OTP delivery.</li>
        <li>Authorities where required by law.</li>
      </ul>

      <h2>4. Storage, security and transfers</h2>
      <ul>
        <li>Data is encrypted in transit (TLS). Sensitive credentials (e.g. Meta access tokens) are encrypted at rest.</li>
        <li>Access is role-restricted and tenant-isolated at the database level (row-level security).</li>
        <li>
          Our infrastructure may process data on servers located outside India (e.g. Singapore) as permitted
          under the DPDP Act. If the Government of India restricts a destination, we will migrate storage
          accordingly.
        </li>
      </ul>

      <h2>5. Retention</h2>
      <ul>
        <li>Account and business data: while your account is active.</li>
        <li>Lead data: while your account is active, so you keep your customer history.</li>
        <li>Invoices and billing records: as required by tax law (typically 8 years).</li>
        <li>On account closure: we delete or anonymise personal data within 30 days of your request, except records we must keep by law.</li>
      </ul>

      <h2>6. Your rights (DPDP Act)</h2>
      <ul>
        <li><strong>Access</strong> — a summary of your personal data and how it is processed.</li>
        <li><strong>Correction and erasure</strong> — fix inaccurate data or ask us to delete it.</li>
        <li><strong>Withdraw consent</strong> — at any time; the Service (or the affected part) stops for you.</li>
        <li><strong>Grievance redressal</strong> — raise a complaint and receive a response.</li>
        <li><strong>Nominate</strong> — name a person to exercise your rights if you are unable to.</li>
      </ul>
      <p>
        To exercise any right, email <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a> from your
        registered contact or write from within the app. We verify requests against your registered mobile
        number.
      </p>

      <h2>7. Grievance Officer</h2>
      <p>
        {COMPANY.grievanceOfficer} — <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a> ({COMPANY.supportHours}).
        We acknowledge grievances within 72 hours and aim to resolve them within 30 days. If you are not
        satisfied, you may complain to the Data Protection Board of India.
      </p>

      <h2>8. Children</h2>
      <p>The Service is for business use by adults and is not directed at children under 18.</p>

      <h2>9. Cookies and local storage</h2>
      <p>
        The app stores your session and language preference on your device (local storage / cookies) so you
        stay signed in and see your chosen language. We do not use third-party advertising cookies on our
        site.
      </p>

      <h2>10. Changes</h2>
      <p>
        We may update this Policy. Material changes are notified in-app or by message to your registered
        number before they take effect.
      </p>

      <h2>11. Contact</h2>
      <p>
        Privacy questions: <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a>.
      </p>
    </LegalShell>
  );
}
