"use client";

/**
 * Shared chrome for the PUBLIC (logged-out) pages: landing + legal.
 * Razorpay activation reviews the website for Terms / Privacy / Refunds / Contact and
 * visible pricing — every public page links all of them from one footer.
 */
import Link from "next/link";
import { COMPANY } from "@/lib/company";
import { LANGUAGES, useI18n } from "@/lib/i18n";
import { Wordmark } from "@/components/ui";

export function PublicHeader() {
  const { locale, setLocale } = useI18n();
  return (
    <header className="flex items-center justify-between gap-3 px-6 py-4">
      <Link href="/" aria-label="Salmor home">
        <Wordmark className="text-lg" />
      </Link>
      <div className="flex items-center gap-1">
        {LANGUAGES.map((l) => (
          <button
            key={l.code}
            onClick={() => setLocale(l.code)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              locale === l.code ? "bg-brand text-white" : "text-ink-muted hover:text-ink"
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>
    </header>
  );
}

export function PublicFooter() {
  const { t } = useI18n();
  const links = [
    { href: "/terms", label: t("footer.terms", "Terms & Conditions") },
    { href: "/privacy", label: t("footer.privacy", "Privacy Policy") },
    { href: "/refunds", label: t("footer.refunds", "Refunds & Cancellation") },
    { href: "/contact", label: t("footer.contact", "Contact Us") },
  ];
  return (
    <footer className="mt-12 border-t border-slate-100 px-6 py-8 text-center">
      <Wordmark className="justify-center text-base" />
      <p className="mx-auto mt-2 max-w-sm text-xs text-ink-muted deva">
        {t("footer.tagline", "Your Saathi for ads & WhatsApp leads — built for Indian small businesses.")}
      </p>
      <nav className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
        {links.map((l) => (
          <Link key={l.href} href={l.href} className="text-xs font-medium text-ink-soft hover:text-brand">
            {l.label}
          </Link>
        ))}
      </nav>
      <p className="mt-4 text-2xs text-ink-faint">
        © {new Date().getFullYear()} {COMPANY.legalName} ·{" "}
        <a href={`mailto:${COMPANY.email}`} className="underline decoration-slate-300 underline-offset-2">
          {COMPANY.email}
        </a>
      </p>
    </footer>
  );
}

/** Prose wrapper for the legal pages — consistent width, type scale and footer. */
export function LegalShell({ title, updated, children }: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-[100dvh]">
      <PublicHeader />
      <article className="mx-auto max-w-2xl px-6 pb-4 pt-6">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="mt-1 text-xs text-ink-faint">Last updated: {updated}</p>
        <div className="legal-prose mt-6">{children}</div>
      </article>
      <PublicFooter />
    </main>
  );
}
