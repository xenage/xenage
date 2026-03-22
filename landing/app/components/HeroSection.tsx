"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { Terminal, ArrowRight, Zap, Copy, CheckCircle2 } from "lucide-react";

export default function HeroSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [copied, setCopied] = useState(false);

  const copyInstall = async () => {
    await navigator.clipboard.writeText("curl https://xenage.dev | bash");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".hero-badge", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.2,
        ease: "power3.out",
      });
      gsap.from(".hero-title", {
        y: 50,
        opacity: 0,
        duration: 1,
        delay: 0.35,
        ease: "power3.out",
      });
      gsap.from(".hero-subtitle", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.5,
        ease: "power3.out",
      });
      gsap.from(".hero-install", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: 0.65,
        ease: "power3.out",
      });
      gsap.from(".hero-actions", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.8,
        ease: "power3.out",
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      className="scroll-section"
      style={{
        padding: "8rem 2rem 5rem",
      }}
    >
      <div style={{ maxWidth: "760px", display: "flex", flexDirection: "column", alignItems: "inherit" }}>
        <style jsx>{`
          @media (max-width: 1024px) {
            section {
              padding-top: 3.5rem !important;
            }
          }
        `}</style>
        <div
          className="hero-badge"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.5rem 1rem",
            background: "rgba(0, 102, 255, 0.08)",
            border: "1px solid rgba(0, 102, 255, 0.2)",
            borderRadius: "100px",
            fontSize: "0.8rem",
            color: "#0066ff",
            marginBottom: "1.5rem",
          }}
        >
          <Zap size={14} />
          <span>Agent Orchestration Platform</span>
        </div>

        <h1
          className="hero-title"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "clamp(2.5rem, 5vw, 4rem)",
            fontWeight: 700,
            lineHeight: 1.05,
            letterSpacing: "-0.03em",
            color: "#0d0d0d",
            marginBottom: "1.5rem",
          }}
        >
          Run, control and
          <br />
          <span
            style={{
              background:
                "linear-gradient(135deg, #0066ff 0%, #00d4ff 50%, #7b61ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            observe AI agents
          </span>
        </h1>

        <p
          className="hero-subtitle"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "1.15rem",
            color: "#4a4a4a",
            lineHeight: 1.7,
            marginBottom: "2rem",
          }}
        >
          Inspired by Kubernetes and Lens — but built for agents.
          <br />
          The infrastructure platform for teams building with AI.
        </p>

        <div
          className="hero-install"
          style={{
            background: "rgba(255, 255, 255, 0.96)",
            border: "1px solid rgba(0, 102, 255, 0.3)",
            borderRadius: "12px",
            padding: "1rem 1.5rem",
            marginBottom: "2rem",
            maxWidth: "420px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              marginBottom: "0.5rem",
            }}
          >
            <Terminal size={18} style={{ color: "#00d4ff" }} />
            <code
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontSize: "0.95rem",
                color: "#0d0d0d",
                flex: 1,
                minWidth: 0,
              }}
            >
              curl https://xenage.dev | bash
            </code>
            <button
              type="button"
              onClick={copyInstall}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "34px",
                height: "34px",
                borderRadius: "8px",
                border: "1px solid rgba(0, 212, 255, 0.35)",
                background: "rgba(0, 102, 255, 0.08)",
                color: copied ? "#0066ff" : "rgba(13, 13, 13, 0.68)",
                cursor: "pointer",
                flexShrink: 0,
              }}
              aria-label="Copy install command"
              title="Copy command"
            >
              {copied ? <CheckCircle2 size={16} /> : <Copy size={16} />}
            </button>
          </div>
          <p
            style={{
              fontSize: "0.8rem",
              color: "#4a4a4a",
              margin: 0,
            }}
          >
            One-command installation or choose from packages below
          </p>
        </div>

        <div
          className="hero-actions"
          style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}
        >
          <a
            href="#install"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.875rem 1.5rem",
              background: "linear-gradient(135deg, #0066ff 0%, #0a7dff 100%)",
              border: "none",
              borderRadius: "8px",
              color: "#fafafa",
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              textDecoration: "none",
              cursor: "pointer",
              transition: "all 0.3s ease",
            }}
          >
            <span>View Packages</span>
            <ArrowRight size={18} />
          </a>
          <a
            href="#problems"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.875rem 1.5rem",
              background: "transparent",
              border: "1.5px solid #0d0d0d",
              borderRadius: "8px",
              color: "#0d0d0d",
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              textDecoration: "none",
              cursor: "pointer",
              transition: "all 0.3s ease",
            }}
          >
            Learn More
          </a>
        </div>
      </div>
    </section>
  );
}
