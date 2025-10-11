import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mission Challenge Dashboard",
  description: "Enhanced mission tracking dashboard powered by FastAPI backend.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
