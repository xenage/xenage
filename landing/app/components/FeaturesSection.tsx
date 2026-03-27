"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { Network, Eye, Box, Layers } from "lucide-react";

const features = [
  {
    icon: Network,
    title: "Zero-Config Connectivity",
    description:
      "Agents auto-discover and connect to control plane. No open ports, no VPN, no hassle.",
  },
  {
    icon: Eye,
    title: "Full Observability",
    description:
      "Real-time monitoring, event logging, and execution traces for all agent systems.",
  },
  {
    icon: Box,
    title: "Isolated Environments",
    description:
      "Agents create other agents, sharing context while staying strictly isolated from other projects.",
  },
  {
    icon: Layers,
    title: "Event-Driven Architecture",
    description:
      "Built for HA with automatic failover and event sourcing for complete audit trails.",
  },
];

export default function FeaturesSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".feature-card", {
        y: 40,
        duration: 0.6,
        stagger: 0.1,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".features-grid",
          start: "top 80%",
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="features"
      className="scroll-section"
      style={{
        padding: "4rem 2rem",
      }}
    >
      <div style={{ maxWidth: "760px", width: "100%", display: "flex", flexDirection: "column", alignItems: "inherit" }}>
        <p
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "0.75rem",
            color: "#0066ff",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            marginBottom: "0.75rem",
          }}
        >
          Features
        </p>

        <h2
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "clamp(1.5rem, 3.5vw, 2rem)",
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            color: "#0d0d0d",
            marginBottom: "2rem",
          }}
        >
          Everything you need to{" "}
          <span
            style={{
              background:
                "linear-gradient(135deg, #0066ff 0%, #00d4ff 50%, #7b61ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            orchestrate agents
          </span>
        </h2>

        <div
          className="features-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "1rem",
            width: "100%",
          }}
        >
          {features.map((feature, i) => (
            <div
              key={i}
              className="feature-card"
              style={{
                padding: "1.25rem",
                background: "rgba(255, 255, 255, 0.9)",
                border: "1px solid rgba(0, 0, 0, 0.06)",
                borderRadius: "12px",
                transition: "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            >
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "rgba(0, 102, 255, 0.08)",
                  border: "1px solid rgba(0, 102, 255, 0.15)",
                  borderRadius: "10px",
                  color: "#0066ff",
                  marginBottom: "0.875rem",
                }}
              >
                <feature.icon size={20} />
              </div>
              <h3
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  color: "#0d0d0d",
                  marginBottom: "0.375rem",
                }}
              >
                {feature.title}
              </h3>
              <p
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.8rem",
                  color: "#4a4a4a",
                  lineHeight: 1.5,
                  margin: 0,
                }}
              >
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
