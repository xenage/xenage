"use client";

import { useEffect, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import HeroCanvas from "./components/HeroCanvas";
import Navigation from "./components/Navigation";
import HeroSection from "./components/HeroSection";
import ProblemsSection from "./components/ProblemsSection";
import InstallSection from "./components/InstallSection";
import FeaturesSection from "./components/FeaturesSection";
import ScaleSection from "./components/ScaleSection";
import GuiSection from "./components/GuiSection";
import PackagesSection from "./components/PackagesSection";
import CtaSection from "./components/CtaSection";
import Footer from "./components/Footer";

gsap.registerPlugin(ScrollTrigger);

export default function Home() {
  const [activeSection, setActiveSection] = useState(0);
  const [seamClip, setSeamClip] = useState("polygon(0% 0%, 76% 0%, 72% 100%, 0% 100%)");
  const [seamClipSoft, setSeamClipSoft] = useState(
    "polygon(0% 0%, 81% 0%, 77% 100%, 0% 100%)",
  );

  const createSeamClip = (seedOffset: number, base: number, variation: number) => {
    const points: string[] = ["0% 0%"];
    const steps = 20;
    let x = base + ((Math.sin(seedOffset * 1.79) + 1) * 0.5 - 0.5) * variation;
    points.push(`${x.toFixed(2)}% 0%`);

    for (let i = 1; i <= steps; i += 1) {
      const y = (i / steps) * 100;
      const waveA = Math.sin(seedOffset * 1.7 + i * 0.74) * variation * 0.52;
      const waveB = Math.cos(seedOffset * 0.82 + i * 1.16) * variation * 0.28;
      x = Math.max(48, Math.min(96, base + waveA + waveB));
      points.push(`${x.toFixed(2)}% ${y.toFixed(2)}%`);
    }

    points.push("0% 100%");
    return `polygon(${points.join(", ")})`;
  };

  useEffect(() => {
    const prevScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    window.scrollTo(0, 0);

    const resetOnPageShow = () => {
      window.scrollTo(0, 0);
    };

    window.addEventListener("pageshow", resetOnPageShow);

    const handleScroll = () => {
      const sections = document.querySelectorAll(".scroll-section");
      sections.forEach((section, i) => {
        const rect = section.getBoundingClientRect();
        const isVisible =
          rect.top < window.innerHeight * 0.6 &&
          rect.bottom > window.innerHeight * 0.4;
        if (isVisible) {
          setActiveSection(i);
        }
      });
    };

    window.addEventListener("scroll", handleScroll);
    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("pageshow", resetOnPageShow);
      window.history.scrollRestoration = prevScrollRestoration;
    };
  }, []);

  useEffect(() => {
    const seed = activeSection + 1.137;
    setSeamClip(createSeamClip(seed, 76, 16));
    setSeamClipSoft(createSeamClip(seed + 0.61, 82, 11));
  }, [activeSection]);

  return (
    <div className="page-wrapper">
      <Navigation />
      <div className="desktop-shell theme-light">
        <div className="canvas-layer">
          <div className="canvas-wall" style={{ clipPath: seamClip }} />
          <div className="canvas-wall-highlight" style={{ clipPath: seamClipSoft }} />
          <HeroCanvas activeSection={activeSection} />
        </div>
        <div className="content-wrapper">
          <HeroSection />
          <ProblemsSection />
          <InstallSection />
          <FeaturesSection />
          <ScaleSection />
          <GuiSection />
          <PackagesSection />
          <CtaSection />
        </div>
      </div>
      <div className="footer-wrapper">
        <Footer />
      </div>

      <style jsx>{`
        .page-wrapper {
          position: relative;
          min-height: 100vh;
          background: linear-gradient(120deg, #fafbfd 0%, #f4f7fd 52%, #eef3fc 100%);
        }

        .desktop-shell {
          position: relative;
          min-height: 100vh;
          z-index: 0;
        }

        .canvas-layer {
          position: fixed;
          right: 0;
          width: 40vw;
          top: 0;
          height: 100vh;
          z-index: 30;
          overflow: hidden;
          pointer-events: auto;
          background: transparent;
          opacity: 1;
        }

        .canvas-wall {
          position: absolute;
          top: 0;
          left: 0;
          width: 52%;
          height: 100%;
          z-index: 26;
          pointer-events: none;
          background: linear-gradient(
            90deg,
            var(--seam-bg-solid) 0%,
            var(--seam-bg-solid) 58%,
            var(--seam-bg-soft) 78%,
            rgba(0, 0, 0, 0) 100%
          );
          transition: clip-path 520ms cubic-bezier(0.22, 1, 0.36, 1);
        }

        .canvas-wall-highlight {
          position: absolute;
          inset: 0 auto 0 0;
          width: 52%;
          z-index: 27;
          pointer-events: none;
          background:
            radial-gradient(56px 30px at 74% 8%, rgba(255, 255, 255, 0.35), transparent 70%),
            radial-gradient(46px 28px at 70% 32%, rgba(255, 255, 255, 0.3), transparent 72%),
            radial-gradient(62px 34px at 76% 58%, rgba(255, 255, 255, 0.28), transparent 70%),
            radial-gradient(44px 28px at 72% 84%, rgba(255, 255, 255, 0.28), transparent 72%);
          opacity: 0.85;
          transition: clip-path 600ms cubic-bezier(0.22, 1, 0.36, 1);
        }

        .content-wrapper {
          position: relative;
          width: 80vw;
          min-width: 0;
          background: #f5f7fd !important;
        }

        .content-wrapper :global(section) {
          position: relative;
          z-index: 30;
          padding-inline: clamp(1.4rem, 2.8vw, 3.2rem) !important;
          background: transparent;
        }

        .content-wrapper :global(section)::before {
          content: "";
          position: absolute;
          inset: 0;
          z-index: -1;
          pointer-events: none;
          background: transparent;
        }

        .content-wrapper :global(section > div) {
          position: relative;
          z-index: 1;
          width: 80% !important;
          max-width: 80% !important;
          margin-left: auto !important;
          margin-right: auto !important;
        }

        .content-wrapper :global([class*="card"]),
        .content-wrapper :global(.scale-point),
        .content-wrapper :global(.hero-install) {
          position: relative !important;
          z-index: 42 !important;
        }

        .content-wrapper :global(.platforms-grid),
        .content-wrapper :global(.features-grid),
        .content-wrapper :global(.scale-points),
        .content-wrapper :global(.gui-grid),
        .content-wrapper :global(.pkg-grid) {
          position: relative !important;
          z-index: 42 !important;
        }

        .footer-wrapper {
          position: relative;
          z-index: 45;
          width: 100%;
        }

        .theme-light {
          --seam-bg-solid: rgba(244, 247, 253, 0.98);
          --seam-bg-soft: rgba(244, 247, 253, 0.6);
        }

        @media (max-width: 1200px) {
          .canvas-layer {
            width: 38vw;
          }

          .content-wrapper {
            width: 82vw;
            background: transparent !important;
          }
        }

        @media (max-width: 1024px) {
          .canvas-layer {
            display: none;
          }

          .content-wrapper {
            width: 100%;
            background: transparent !important;
            border-right: none;
          }

          .content-wrapper :global(section)::before {
            z-index: 0;
          }

          .content-wrapper :global(section > div) {
            margin-left: auto;
          }

        }
      `}</style>
    </div>
  );
}
