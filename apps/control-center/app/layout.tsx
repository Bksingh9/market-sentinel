import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Market Sentinel Control Center",
  description: "Safe-by-default trading scaffold operations dashboard.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
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
