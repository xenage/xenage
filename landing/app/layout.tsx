import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Xenage — Agent Orchestration Platform",
  description:
    "Run, control and observe AI agents across infinite clusters. Inspired by Kubernetes and Lens — built for agents.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
