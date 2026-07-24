import type { Metadata } from "next";
import { COMPANY, PRICING, TRIAL_DAYS } from "@/lib/company";
import { LegalShell } from "@/components/public";

export const metadata: Metadata = {
  title: "Terms & Conditions — Salmor",
  description: "Terms and conditions for using the Salmor service.",
};

const UPDATED = "24 July 2026";

export default function Terms() {
  return (
    <LegalShell title="Terms & Conditions" updated={UPDATED}>
      <p>
        These Terms & Conditions (&ldquo;Terms&rdquo;) govern your use of the {COMPANY.name} platform and
        related services (the &ldquo;Service&rdquo;) provided by {COMPANY.legalName} (&ldquo;we&rdquo;,
        &ldquo;us&rdquo;, &ldquo;our&rdquo;). By creating an account or using the Service you agree to these
        Terms and to our <a href="/privacy">Privacy Policy</a>.
      </p>

      <h2>1. What the Service is</h2>
      <p>
        {COMPANY.name} is an AI-assisted advertising and lead-management service for businesses. It helps you
        create, launch and optimise ads on Meta platforms (Facebook and Instagram), and receives, greets and
        qualifies the resulting enquiries (&ldquo;leads&rdquo;) — primarily over WhatsApp — so you can follow
        up with interested customers.
      </p>
      <p>
        The Service automates work on your behalf, always within controls you set: you approve campaigns
        before launch (or explicitly enable autopilot), you set budgets and daily caps, and you can pause
        advertising at any time.
      </p>

      <h2>2. Eligibility and your account</h2>
      <ul>
        <li>The Service is for business use by persons aged 18 or over.</li>
        <li>You must provide accurate business information and keep it up to date.</li>
        <li>
          Login is via one-time password (OTP) to your mobile number. You are responsible for activity on
          your account and for keeping your device and number secure.
        </li>
      </ul>

      <h2>3. Your responsibilities</h2>
      <ul>
        <li>Your business, products and advertising claims must be lawful in India.</li>
        <li>
          Ads run under your business identity and (where connected) your own Meta ad account and Page. You
          are responsible for complying with Meta&rsquo;s Advertising Standards and the WhatsApp Business
          messaging policies.
        </li>
        <li>
          Ad spend is charged by Meta to the payment method on your ad account. It is separate from our
          platform fee and never collected by us (see Section 4).
        </li>
        <li>
          You must have the right to contact the leads you manage through the Service and to use their
          information (see our <a href="/privacy">Privacy Policy</a>).
        </li>
      </ul>

      <h2>4. Fees, billing and trial</h2>
      <ul>
        <li>
          The platform fee is a monthly subscription per our published pricing (currently{" "}
          {PRICING.map((p) => `${p.tier.charAt(0) + p.tier.slice(1).toLowerCase()} ₹${p.priceInr.toLocaleString("en-IN")}`).join(", ")}{" "}
          per month, plus GST). Prices may change with notice; changes apply from your next billing cycle.
        </li>
        <li>Every plan starts with a {TRIAL_DAYS}-day free trial.</li>
        <li>
          Subscriptions are billed monthly in advance through our payment partner (Razorpay), typically via
          UPI Autopay mandate. A GST invoice is issued for every charge.
        </li>
        <li>
          Your advertising budget is separate: it stays in your own ad account and is paid by you directly
          to Meta.
        </li>
        <li>
          Cancellation and refunds are governed by our <a href="/refunds">Refunds & Cancellation Policy</a>.
        </li>
      </ul>

      <h2>5. Acceptable use</h2>
      <p>You must not use the Service to:</p>
      <ul>
        <li>advertise anything illegal, deceptive or prohibited by Meta&rsquo;s or WhatsApp&rsquo;s policies;</li>
        <li>send spam or message people without a lawful basis to contact them;</li>
        <li>upload content that infringes another person&rsquo;s rights;</li>
        <li>probe, disrupt or reverse-engineer the Service.</li>
      </ul>

      <h2>6. AI-generated content</h2>
      <p>
        The Service uses AI models to draft ad copy, images and chat replies. AI output can be imperfect.
        You review and approve campaign content before it goes live (unless you enable autopilot, in which
        case you accept responsibility for content published under your configured settings) and you remain
        responsible for the accuracy of claims made about your own business.
      </p>

      <h2>7. No guarantee of results</h2>
      <p>
        Advertising outcomes depend on your market, offer, budget and the ad platforms themselves. We do not
        guarantee any particular number of leads, cost per lead, or revenue outcome.
      </p>

      <h2>8. Intellectual property</h2>
      <p>
        We own the Service and its software. You own your business information and content you provide, and
        the ad creatives generated for your business through your account may be used by you for your
        business marketing. You grant us the licence needed to operate the Service for you (e.g. to submit
        your creatives and targeting to Meta and to process lead conversations).
      </p>

      <h2>9. Suspension and termination</h2>
      <p>
        You can stop using the Service and cancel at any time. We may suspend or terminate accounts that
        breach these Terms, create legal or platform-policy risk, or fail to pay fees. On termination we
        will, on request, provide an export of your leads within 30 days, after which data is deleted per
        our <a href="/privacy">Privacy Policy</a>.
      </p>

      <h2>10. Disclaimers and limitation of liability</h2>
      <p>
        The Service is provided &ldquo;as is&rdquo;. To the maximum extent permitted by law, we are not
        liable for indirect or consequential losses, loss of profits, or platform actions taken by third
        parties (e.g. Meta ad-account restrictions). Our total aggregate liability for any claim is limited
        to the platform fees you paid us in the three (3) months before the event giving rise to the claim.
      </p>

      <h2>11. Indemnity</h2>
      <p>
        You agree to indemnify us against claims arising from your business content, your advertising
        claims, or your breach of these Terms or applicable law.
      </p>

      <h2>12. Governing law</h2>
      <p>
        These Terms are governed by the laws of India. Disputes are subject to the exclusive jurisdiction of
        the courts at our registered place of business in India.
      </p>

      <h2>13. Changes to these Terms</h2>
      <p>
        We may update these Terms from time to time. Material changes will be notified in-app or by message
        to your registered number, and continued use after the effective date constitutes acceptance.
      </p>

      <h2>14. Contact</h2>
      <p>
        Questions about these Terms: <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a> ({COMPANY.supportHours}).
      </p>
    </LegalShell>
  );
}
