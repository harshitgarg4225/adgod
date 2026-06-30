import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { ToastProvider } from "@/components/ui";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const deva = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  variable: "--font-deva",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Salmor — your Saathi for ads & leads",
  description:
    "Salmor runs your ads and qualifies WhatsApp leads on autopilot — built for Indian small businesses.",
  applicationName: "Salmor",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Salmor", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0B7A4B",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${deva.variable}`}>
      <body>
        <I18nProvider>
          <ToastProvider>
            <div className="app-frame">{children}</div>
          </ToastProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
