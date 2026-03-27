import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://xenage.dev"),
  title: {
    default: "Xenage — Agent Orchestration Platform",
    template: "%s | Xenage",
  },
  description:
    "Run, control, and observe AI agents across clusters. Xenage is the orchestration platform inspired by Kubernetes and Lens, built specifically for agent workloads.",
  keywords: [
    "agent orchestration platform",
    "ai agent infrastructure",
    "ai agent control plane",
    "agent cluster management",
    "multi-agent operations",
    "xenage",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: "https://xenage.dev/",
    siteName: "Xenage",
    title: "Xenage — Agent Orchestration Platform",
    description:
      "Run, control, and observe AI agents across clusters. Built for modern agent teams.",
    images: [
      {
        url: "/xenage.png",
        width: 911,
        height: 356,
        alt: "Xenage platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Xenage — Agent Orchestration Platform",
    description:
      "Run, control, and observe AI agents across clusters with Xenage.",
    images: ["/xenage.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  category: "technology",
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
