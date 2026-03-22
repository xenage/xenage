"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ArrowRight } from "lucide-react";

export default function CtaSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".cta-content", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".cta-content",
          start: "top 80%",
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      className="scroll-section"
      style={{
        padding: "5rem 2rem",
        textAlign: "center",
      }}
    >
      <div style={{ maxWidth: "560px", width: "100%", margin: "0 auto", display: "flex", flexDirection: "column", alignItems: "inherit" }}>
        <h2
          className="cta-content"
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
          Ready to{" "}
          <span
            style={{
              background:
                "linear-gradient(135deg, #0066ff 0%, #00d4ff 50%, #7b61ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            orchestrate
          </span>
          ?
        </h2>

        <p
          className="cta-content"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "1rem",
            color: "#4a4a4a",
            lineHeight: 1.6,
            marginBottom: "2rem",
          }}
        >
          Join the future of agent infrastructure.
          <br />
          Ship faster, scale infinitely, maintain control.
        </p>

        <div
          className="cta-content"
          style={{
            display: "flex",
            gap: "1rem",
            justifyContent: "center",
            flexWrap: "wrap",
          }}
        >
          <a
            href="#install"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.875rem 1.75rem",
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
            <span>Start Building</span>
            <ArrowRight size={18} />
          </a>
          <a
            href="https://docs.xenage.dev"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.875rem 1.75rem",
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
            Documentation
          </a>
        </div>
      </div>
    </section>
  );
}
