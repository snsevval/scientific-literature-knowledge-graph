import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ActiveScience v2",
  description: "Multi-Agent Knowledge Graph System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}