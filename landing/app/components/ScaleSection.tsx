"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import {
  Shield,
  Server,
  Laptop,
  Smartphone,
  Cpu,
  Globe,
  Lock,
  Zap,
} from "lucide-react";

const scalePoints = [
  {
    icon: Globe,
    title: "Multi-Cluster",
    description:
      "Deploy across custom clusters. Copy & Paste configs between them.",
  },
  {
    icon: Server,
    title: "HA Mode",
    description:
      "Agents run on servers, laptops, phones. Auto-connect to control plane.",
  },
  {
    icon: Lock,
    title: "Scoped RBAC",
    description:
      "Grant granular access to agents. Full audit trail, zero trust.",
  },
  {
    icon: Zap,
    title: "Event-Driven",
    description: "Automatic failover, event sourcing, complete observability.",
  },
];

export default function ScaleSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".scale-header", {
        y: 30,
        opacity: 0,
        duration: 0.6,
        stagger: 0.1,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".scale-header",
          start: "top 80%",
        },
      });

      gsap.from(".scale-diagram", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".scale-diagram",
          start: "top 80%",
        },
      });

      gsap.from(".scale-point", {
        x: -30,
        duration: 0.5,
        stagger: 0.1,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".scale-points",
          start: "top 80%",
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="scale"
      className="scroll-section"
      style={{
        padding: "4rem 2rem",
      }}
    >
      <div style={{ maxWidth: "760px", width: "100%", display: "flex", flexDirection: "column", alignItems: "inherit" }}>
        <p
          className="scale-header"
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "0.75rem",
            color: "#00d4ff",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            marginBottom: "0.75rem",
          }}
        >
          Architecture
        </p>

        <h2
          className="scale-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "clamp(1.5rem, 3.5vw, 2rem)",
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            color: "#0d0d0d",
            marginBottom: "1rem",
          }}
        >
          Built for{" "}
          <span
            style={{
              background:
                "linear-gradient(135deg, #0066ff 0%, #00d4ff 50%, #7b61ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            infinite scale
          </span>
        </h2>

        <p
          className="scale-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "0.95rem",
            color: "#4a4a4a",
            marginBottom: "2.5rem",
          }}
        >
          The IDE for startups and teams. Manage agent systems that build and
          test products.
        </p>

        <div
          className="scale-diagram"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "1.5rem",
            marginBottom: "2.5rem",
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "0.75rem",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.875rem 1.75rem",
                background: "rgba(0, 102, 255, 0.15)",
                border: "1px solid rgba(0, 102, 255, 0.4)",
                borderRadius: "12px",
              }}
            >
              <Shield size={18} style={{ color: "#00d4ff" }} />
              <span
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.9rem",
                  fontWeight: 600,
                  color: "#0d0d0d",
                }}
              >
                xenage control-plane
              </span>
            </div>

            <div
              style={{
                display: "flex",
                gap: "3.5rem",
              }}
            >
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  style={{
                    width: "2px",
                    height: "30px",
                    background:
                      "linear-gradient(180deg, rgba(0, 102, 255, 0.6), transparent)",
                  }}
                />
              ))}
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "1rem",
              flexWrap: "wrap",
              justifyContent: "center",
            }}
          >
            {[
              { icon: Server, label: "Server" },
              { icon: Laptop, label: "Laptop" },
              { icon: Smartphone, label: "Mobile" },
              { icon: Cpu, label: "Edge" },
            ].map((node, i) => (
              <div
                key={i}
                className="scale-node-card"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "0.375rem",
                  padding: "1rem",
                  background: "rgba(255, 255, 255, 0.92)",
                  border: "1px solid rgba(0, 0, 0, 0.08)",
                  borderRadius: "10px",
                  minWidth: "85px",
                }}
              >
                <node.icon
                  size={20}
                  style={{ color: "rgba(13, 13, 13, 0.72)" }}
                />
                <span
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.7rem",
                    color: "#4a4a4a",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  {node.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div
          className="scale-points"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "0.875rem",
            width: "100%",
          }}
        >
          {scalePoints.map((point, i) => (
            <div
              key={i}
              className="scale-point"
              style={{
                display: "flex",
                gap: "0.875rem",
                padding: "1rem",
                background: "rgba(255, 255, 255, 0.94)",
                border: "1px solid rgba(0, 0, 0, 0.08)",
                borderRadius: "10px",
              }}
            >
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "rgba(0, 102, 255, 0.1)",
                  border: "1px solid rgba(0, 102, 255, 0.2)",
                  borderRadius: "8px",
                  color: "#00d4ff",
                  flexShrink: 0,
                }}
              >
                <point.icon size={16} />
              </div>
              <div>
                <h4
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    color: "#0d0d0d",
                    marginBottom: "0.25rem",
                  }}
                >
                  {point.title}
                </h4>
                <p
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.75rem",
                    color: "#4a4a4a",
                    lineHeight: 1.4,
                    margin: 0,
                  }}
                >
                  {point.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
