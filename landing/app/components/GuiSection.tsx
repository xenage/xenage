"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { Layout, Server, Box, Monitor, Globe, ArrowRight } from "lucide-react";

const guiFeatures = [
  {
    icon: Layout,
    title: "Xenage IDE",
    description: "The unified IDE for startups and teams. Manage agent systems that build and test products. Visual workflow builder with real-time agent monitoring.",
  },
  {
    icon: Server,
    title: "Control Plane GUI",
    description: "Install xenage control-plane on your devices to form a cluster. Monitor all connected agents, manage configurations, and deploy changes.",
  },
  {
    icon: Box,
    title: "Runtime Environment",
    description: "Lightweight runtime for executing agent code. Spawn isolated environments, share context between agents, maintain strict isolation.",
  },
];

export default function GuiSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".gui-header", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".gui-header",
          start: "top 80%",
        },
      });

      gsap.from(".gui-card", {
        y: 60,
        duration: 0.8,
        stagger: 0.15,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".gui-grid",
          start: "top 80%",
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="gui"
      className="scroll-section"
      style={{
        padding: "5rem 2rem",
      }}
    >
      <div style={{ maxWidth: "760px", width: "100%", display: "flex", flexDirection: "column", alignItems: "inherit" }}>
        <p
          className="gui-header"
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "0.8rem",
            color: "#00d4ff",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            marginBottom: "1rem",
          }}
        >
          Graphical Interface
        </p>

        <h2
          className="gui-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "clamp(1.75rem, 4vw, 2.5rem)",
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            color: "#0d0d0d",
            marginBottom: "1rem",
          }}
        >
          The complete<br />
          <span
            style={{
              background: "linear-gradient(135deg, #0066ff 0%, #00d4ff 50%, #7b61ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            GUI experience
          </span>
        </h2>

        <p
          className="gui-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "1rem",
            color: "#4a4a4a",
            marginBottom: "3rem",
          }}
        >
          Three components work together: IDE for orchestration, control-plane for cluster management, runtime for agent execution.
        </p>

        <div
          className="gui-grid"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1.25rem",
          }}
        >
          {guiFeatures.map((feature, i) => (
            <div
              key={i}
              className="gui-card"
              style={{
                display: "flex",
                flexDirection: "row",
                flexWrap: "wrap",
                gap: "1.5rem",
                padding: "1.75rem",
                background: "rgba(255, 255, 255, 0.94)",
                border: "1px solid rgba(0, 0, 0, 0.08)",
                borderRadius: "16px",
                transition: "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            >
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "rgba(0, 102, 255, 0.1)",
                  border: "1px solid rgba(0, 102, 255, 0.25)",
                  borderRadius: "12px",
                  color: "#00d4ff",
                  flexShrink: 0,
                }}
              >
                <feature.icon size={26} />
              </div>
              <div style={{ flex: 1 }}>
                <h3
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "1.1rem",
                    fontWeight: 600,
                    color: "#0d0d0d",
                    marginBottom: "0.5rem",
                  }}
                >
                  {feature.title}
                </h3>
                <p
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.9rem",
                    color: "#4a4a4a",
                    lineHeight: 1.65,
                    margin: 0,
                  }}
                >
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
}
