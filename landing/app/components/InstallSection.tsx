"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { Terminal, Download, Monitor, Smartphone, Globe } from "lucide-react";

const platforms = [
  {
    id: "win-x64",
    name: "Windows x86_64",
    icon: Monitor,
    asset: "xenage-win-x64.exe",
  },
  {
    id: "win-arm",
    name: "Windows ARM64",
    icon: Smartphone,
    asset: "xenage-win-arm64.exe",
  },
  {
    id: "linux-x64",
    name: "Linux x86_64",
    icon: Globe,
    asset: "xenage-linux-x64",
  },
  {
    id: "linux-arm",
    name: "Linux ARM64",
    icon: Globe,
    asset: "xenage-linux-arm64",
  },
  {
    id: "mac-x64",
    name: "macOS Intel",
    icon: Monitor,
    asset: "xenage-macos-x64",
  },
  {
    id: "mac-arm",
    name: "macOS Apple Silicon",
    icon: Monitor,
    asset: "xenage-macos-arm64",
  },
];

export default function InstallSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [recommendedPlatform, setRecommendedPlatform] = useState<string | null>(
    null,
  );

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".install-header", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".install-header",
          start: "top 80%",
        },
      });

      gsap.from(".platform-card", {
        y: 24,
        duration: 0.5,
        stagger: 0.08,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ".platforms-grid",
          start: "top 80%",
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  useEffect(() => {
    const ua = navigator.userAgent.toLowerCase();
    const isArm =
      ua.includes("arm64") ||
      ua.includes("aarch64") ||
      ua.includes("apple") ||
      ua.includes("silicon");

    if (ua.includes("windows")) {
      setRecommendedPlatform(isArm ? "win-arm" : "win-x64");
      return;
    }
    if (ua.includes("mac os") || ua.includes("macintosh")) {
      setRecommendedPlatform(isArm ? "mac-arm" : "mac-x64");
      return;
    }
    if (ua.includes("linux")) {
      setRecommendedPlatform(isArm ? "linux-arm" : "linux-x64");
      return;
    }
    setRecommendedPlatform(null);
  }, []);

  const releaseBase = "https://github.com/xenage/xenage/releases/latest/download";

  return (
    <section
      ref={sectionRef}
      id="install"
      className="scroll-section"
      style={{
        padding: "5rem 2rem",
      }}
    >
      <div style={{ maxWidth: "760px", width: "100%", display: "flex", flexDirection: "column", alignItems: "inherit" }}>
        <p
          className="install-header"
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: "0.8rem",
            color: "#0066ff",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            marginBottom: "1rem",
          }}
        >
          Installation
        </p>

        <h2
          className="install-header"
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
          Choose your
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
            starting point
          </span>
        </h2>

        <p
          className="install-header"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "1rem",
            color: "#4a4a4a",
            marginBottom: "2rem",
          }}
        >
          Download xenage CLI for your platform or use the quick install
        </p>

        <div
          className="install-command-card"
          style={{
            background: "rgba(255, 255, 255, 0.96)",
            border: "1px solid rgba(0, 102, 255, 0.3)",
            borderRadius: "12px",
            padding: "1.25rem 1.5rem",
            marginBottom: "2rem",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
            }}
          >
            <Terminal size={20} style={{ color: "#00d4ff" }} />
            <code
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontSize: "1rem",
                color: "#0d0d0d",
                flex: 1,
              }}
            >
              curl https://xenage.dev | bash
            </code>
          </div>
        </div>

        <div
          className="platforms-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "0.75rem",
            width: "100%",
            marginBottom: "2rem",
          }}
        >
          {platforms.map((platform) => {
            const isRecommended = platform.id === recommendedPlatform;
            return (
              <a
              key={platform.id}
              className="platform-card"
              href={`${releaseBase}/${platform.asset}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "0.5rem",
                padding: "1rem 0.75rem",
                background: isRecommended
                  ? "linear-gradient(180deg, rgba(0,102,255,0.11), rgba(255,255,255,0.95))"
                  : "rgba(255, 255, 255, 0.94)",
                border: isRecommended
                  ? "1px solid rgba(0, 102, 255, 0.46)"
                  : "1px solid rgba(0, 0, 0, 0.06)",
                borderRadius: "10px",
                cursor: "pointer",
                transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                textDecoration: "none",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-3px)";
                e.currentTarget.style.borderColor = "rgba(0, 102, 255, 0.3)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.borderColor = isRecommended
                  ? "rgba(0, 102, 255, 0.46)"
                  : "rgba(0, 0, 0, 0.06)";
              }}
            >
              <platform.icon size={24} style={{ color: "#0066ff" }} />
              <span
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.8rem",
                  fontWeight: 500,
                  color: "#0d0d0d",
                  textAlign: "center",
                }}
                >
                  {platform.name}
                </span>
                <Download size={14} style={{ color: "#4a4a4a" }} />
                {isRecommended ? (
                  <span
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "0.65rem",
                      color: "#0066ff",
                      letterSpacing: "0.05em",
                      textTransform: "uppercase",
                    }}
                  >
                    Your platform
                  </span>
                ) : null}
              </a>
            );
          })}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <a
            href="#features"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              color: "#0066ff",
              textDecoration: "none",
              fontWeight: 500,
            }}
          >
            Explore all features
          </a>
        </div>
      </div>
    </section>
  );
}
