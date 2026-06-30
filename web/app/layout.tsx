import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Salmor — Saathi",
  description: "Qualified WhatsApp leads on autopilot for Indian SMBs.",
  manifest: undefined,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0B7A4B",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-md min-h-screen bg-white shadow-sm">{children}</div>
      </body>
    </html>
  );
}
