import type { Metadata } from "next";
import { COMPANY, TRIAL_DAYS } from "@/lib/company";
import { LegalShell } from "@/components/public";

export const metadata: Metadata = {
  title: "Refunds & Cancellation — Salmor",
  description: "Salmor's cancellation and refund policy for subscriptions and wallet balances.",
};

const UPDATED = "24 July 2026";

export default function Refunds() {
  return (
    <LegalShell title="Refunds & Cancellation Policy" updated={UPDATED}>
      <p>
        This policy covers the {COMPANY.name} <strong>platform subscription</strong> and optional
        <strong> wallet</strong> balances. It does not cover advertising spend, which you pay directly to
        Meta from your own ad account and which we never collect.
      </p>

      <h2>1. Free trial</h2>
      <p>
        Every plan starts with a {TRIAL_DAYS}-day free trial. You are not charged during the trial, and you
        can cancel within it at no cost.
      </p>

      <h2>2. Cancelling your subscription</h2>
      <ul>
        <li>
          Cancel anytime — from the <strong>Billing</strong> section in the app, or by emailing{" "}
          <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a> from your registered contact.
        </li>
        <li>
          Cancellation takes effect at the end of the current billing period. You keep access until then.
        </li>
        <li>Cancelling also cancels the UPI Autopay mandate for future charges.</li>
      </ul>

      <h2>3. Refunds</h2>
      <ul>
        <li>
          <strong>Partial months:</strong> subscription fees are billed monthly in advance and are not
          refunded pro-rata for time you did not use within a paid month.
        </li>
        <li>
          <strong>Duplicate, failed or erroneous charges:</strong> refunded in full once verified. Write to
          us with the payment reference; refunds are initiated within 5–7 business days to the original
          payment method (bank timelines may add a few days).
        </li>
        <li>
          <strong>Service failure:</strong> if a verified platform outage on our side prevented the Service
          from operating for a substantial part of a paid period, we will credit or refund fairly for the
          affected period.
        </li>
      </ul>

      <h2>4. Wallet balances</h2>
      <p>
        If your plan includes a wallet, unused wallet balance is refundable on account closure: request it
        in writing from your registered contact and we will return the unused balance to your original
        payment method within 7–10 business days, less any taxes or gateway charges that cannot be reversed.
      </p>

      <h2>5. Advertising spend</h2>
      <p>
        Ad budgets are charged by Meta directly to the payment method on your ad account, under Meta&rsquo;s
        own terms. We cannot refund money paid to Meta. Pausing your ads in the app stops further spend.
      </p>

      <h2>6. How to reach us</h2>
      <p>
        <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a> ({COMPANY.supportHours}). Please include
        your registered mobile number and, for payment issues, the payment reference ID from your invoice
        or bank statement.
      </p>
    </LegalShell>
  );
}
