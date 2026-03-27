"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { Users, Layers, GitBranch, Lock, Server, Shield } from "lucide-react";

const problems = [
  {
    icon: Users,
    title: "Not a personal assistant",
    description:
      "You don't need another chatbot. You need agents that build products, test hypotheses, and deploy to production.",
  },
  {
    icon: Layers,
    title: "Multi-cluster chaos",
    description:
      "Different tasks require different clusters — personal, games, finance, separate projects. Copying configurations between them should be trivial.",
  },
  {
    icon: GitBranch,
    title: "Git-style everything",
    description:
      "Agents can modify their configs and improve themselves. The system must show diffs, store history, allow rollbacks, and give full control over changes.",
  },
  {
    icon: Lock,
    title: "Isolated execution",
    description:
      "Agents spawn sub-agents, share context and filesystems, sessions and secrets — while staying isolated from other agents and projects.",
  },
  {
    icon: Server,
    title: "HA + Cluster Mode",
    description:
      "Agents shouldn't crash if a server goes down. Run them on different machines — servers, laptops, phones — without opening ports.",
  },
  {
    icon: Shield,
    title: "RBAC Security",
    description:
      "Grant access to agents and workflows to others, while strictly limiting scope of visibility, changes, and permissions.",
  },
];

export default function ProblemsSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        ".problem-card",
        {
          y: 40,
          opacity: 0,
        },
        {
          y: 0,
          opacity: 1,
          duration: 0.6,
          stagger: 0.08,
          ease: "power3.out",
          clearProps: "transform,opacity",
          scrollTrigger: {
            trigger: ".problems-grid",
            start: "top 80%",
            once: true,
          },
        },
      );
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="problems"
      className="scroll-section"
      style={{
        position: "relative",
        padding: "4rem 2rem",
      }}
    >
      <div
        className="problems-container"
        style={{ maxWidth: "1120px", width: "100%", display: "flex", flexDirection: "column" }}
      >
        <div className="problems-intro" style={{ maxWidth: "760px" }}>
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
            The Problem
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
            Personal assistants are{" "}
            <span style={{ color: "#0066ff" }}>not enough</span>
          </h2>
        </div>

        <div
          className="problems-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: "1rem",
            width: "100%",
            alignItems: "stretch",
          }}
        >
          {problems.map((problem, i) => (
            <div
              key={i}
              className="problem-card"
              style={{
                position: "relative",
                zIndex: 50,
                display: "flex",
                gap: "1rem",
                height: "100%",
                padding: "1.25rem",
                background: "rgba(255, 255, 255, 0.8)",
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
                  borderRadius: "8px",
                  color: "#0066ff",
                  flexShrink: 0,
                }}
              >
                <problem.icon size={18} />
              </div>
              <div>
                <h3
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.9rem",
                    fontWeight: 600,
                    color: "#0d0d0d",
                    marginBottom: "0.35rem",
                  }}
                >
                  {problem.title}
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
                  {problem.description}
                </p>
              </div>
            </div>
          ))}
        </div>
        <style jsx>{`
          @media (max-width: 1200px) {
            .problems-grid {
              grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            }
          }

          @media (max-width: 760px) {
            .problems-grid {
              grid-template-columns: minmax(0, 1fr) !important;
            }
            .problems-intro {
              max-width: 100% !important;
            }
          }
        `}</style>
      </div>
    </section>
  );
}
