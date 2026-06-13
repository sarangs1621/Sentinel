import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Sentinel — Observability & Incident Management",
    template: "%s · Sentinel",
  },
  description:
    "Production-grade uptime monitoring, incident detection, and alerting platform. Monitor HTTP, TCP, and PING endpoints with real-time dashboards and SLA reporting.",
  keywords: ["uptime monitoring", "incident management", "observability", "SLA reporting"],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0e1a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
