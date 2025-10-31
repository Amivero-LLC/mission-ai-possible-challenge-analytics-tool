import type { Metadata } from "next";
import "./globals.css";
import { ToastProvider } from "../components/toast/ToastProvider";

export const metadata: Metadata = {
  title: "Mission Challenge Dashboard | Amivero",
  description: "Modern analytics dashboard for tracking mission challenges and AI interactions.",
  applicationName: "Mission:AI Possible",
  manifest: "/site.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Mission:AI Possible",
  },
  formatDetection: {
    telephone: false,
  },
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#667eea" },
    { media: "(prefers-color-scheme: dark)", color: "#667eea" },
  ],
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
