"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import {
  Package,
  Server,
  Terminal,
  Code,
  Layout,
  CheckCircle2,
  Copy,
} from "lucide-react";

const packages = [
  {
    name: "@xenage/core",
    description: "Control plane and agent runtime",
    install: "npm install @xenage/core",
    icon: Server,
  },
  {
    name: "@xenage/cli",
    description: "Command-line interface",
    install: "npm install -g @xenage/cli",
    icon: Terminal,
  },
  {
    name: "@xenage/sdk",
    description: "SDK for agent development",
    install: "npm install @xenage/sdk",
    icon: Code,
  },
  {
    name: "@xenage/ui",
    description: "Web dashboard components",
    install: "npm install @xenage/ui",
    icon: Layout,
  },
];

export default function PackagesSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyInstall = (cmd: string, index: number) => {
    navigator.clipboard.writeText(cmd);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".pkg-header", {
        y: 30,
        opacity: 0,
        duration: 0.6,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".pkg-header",
          start: "top 80%",
        },
      });

      gsap.from(".pkg-card", {
        y: 30,
        duration: 0.5,
        stagger: 0.08,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".pkg-grid",
          start: "top 80%",
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="packages"
      className="scroll-section"
      style={{
        padding: "4rem 2rem",
      }}
    >
      <div style={{ maxWidth: "760px" }}>
        <p
          className="pkg-header"
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "0.75rem",
            color: "#0066ff",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            marginBottom: "0.75rem",
          }}
        >
          Packages
        </p>

        <h2
          className="pkg-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "clamp(1.5rem, 3.5vw, 2rem)",
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            color: "#0d0d0d",
            marginBottom: "0.75rem",
          }}
        >
          Individual packages
        </h2>

        <p
          className="pkg-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "0.9rem",
            color: "#4a4a4a",
            marginBottom: "1.5rem",
          }}
        >
          Install only what you need. Each package is independently versioned.
        </p>

        <div
          className="pkg-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: "0.875rem",
          }}
        >
          {packages.map((pkg, i) => (
            <div
              key={i}
              className="pkg-card"
              style={{
                padding: "1.125rem",
                background: "rgba(255, 255, 255, 0.9)",
                border: "1px solid rgba(0, 0, 0, 0.06)",
                borderRadius: "12px",
                transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  marginBottom: "0.875rem",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "rgba(0, 102, 255, 0.08)",
                    border: "1px solid rgba(0, 102, 255, 0.15)",
                    borderRadius: "8px",
                    color: "#0066ff",
                  }}
                >
                  <pkg.icon size={18} />
                </div>
                <div>
                  <p
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "0.8rem",
                      color: "#0d0d0d",
                      margin: 0,
                      fontWeight: 500,
                    }}
                  >
                    {pkg.name}
                  </p>
                  <p
                    style={{
                      fontFamily: "Space Grotesk, sans-serif",
                      fontSize: "0.75rem",
                      color: "#8a8a8a",
                      margin: 0,
                    }}
                  >
                    {pkg.description}
                  </p>
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.5rem 0.625rem",
                  background: "rgba(0, 102, 255, 0.08)",
                  borderRadius: "6px",
                }}
              >
                <code
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "0.7rem",
                    color: "#0d0d0d",
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {pkg.install}
                </code>
                <button
                  onClick={() => copyInstall(pkg.install, i)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "4px",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    borderRadius: "4px",
                    transition: "all 0.2s ease",
                  }}
                >
                  {copiedIndex === i ? (
                    <CheckCircle2 size={14} style={{ color: "#0066ff" }} />
                  ) : (
                    <Copy
                      size={14}
                      style={{ color: "rgba(255, 255, 255, 0.72)" }}
                    />
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
