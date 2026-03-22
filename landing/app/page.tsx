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

  const [seamClipMobile, setSeamClipMobile] = useState("polygon(0% 100%, 100% 100%, 100% 24%, 0% 28%)");
  const [seamClipSoftMobile, setSeamClipSoftMobile] = useState(
    "polygon(0% 100%, 100% 100%, 100% 19%, 0% 23%)",
  );

  const createSeamClip = (seedOffset: number, base: number, variation: number, horizontal = false) => {
    const points: string[] = horizontal ? [] : ["0% 0%"];
    const steps = 20;
    
    if (!horizontal) {
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
    } else {
      // For mobile: clip-path from top, keeping bottom 100%
      points.push("0% 100%");
      points.push("100% 100%");
      
      let y = base + ((Math.sin(seedOffset * 1.79) + 1) * 0.5 - 0.5) * variation;
      points.push(`100% ${y.toFixed(2)}%`);

      for (let i = 1; i <= steps; i += 1) {
        const x = 100 - (i / steps) * 100;
        const waveA = Math.sin(seedOffset * 1.7 + i * 0.74) * variation * 0.52;
        const waveB = Math.cos(seedOffset * 0.82 + i * 1.16) * variation * 0.28;
        y = Math.max(5, Math.min(45, base + waveA + waveB));
        points.push(`${x.toFixed(2)}% ${y.toFixed(2)}%`);
      }
      points.push("0% 0%");
    }
    
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

    // Mobile opacity animation
    const ctx = gsap.context(() => {
      if (window.innerWidth <= 1024) {
        const sections = document.querySelectorAll(".scroll-section");
        sections.forEach((section) => {
          gsap.fromTo(
            section,
            { opacity: 0 },
            {
              opacity: 1,
              scrollTrigger: {
                trigger: section,
                start: "top 95%",
                end: "top 65%",
                scrub: true,
              },
            }
          );
        });
      }
    });

    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("pageshow", resetOnPageShow);
      window.history.scrollRestoration = prevScrollRestoration;
      ctx.revert();
    };
  }, []);

  useEffect(() => {
    const seed = activeSection + 1.137;
    setSeamClip(createSeamClip(seed, 76, 16));
    setSeamClipSoft(createSeamClip(seed + 0.61, 82, 11));
    setSeamClipMobile(createSeamClip(seed, 26, 12, true));
    setSeamClipSoftMobile(createSeamClip(seed + 0.61, 21, 8, true));
  }, [activeSection]);

  return (
    <div className="page-wrapper">
      <Navigation />
      <div className="desktop-shell theme-light">
        <div className="canvas-layer desktop-canvas">
          <div className="canvas-wall" style={{ clipPath: seamClip }} />
          <div className="canvas-wall-highlight" style={{ clipPath: seamClipSoft }} />
          <HeroCanvas activeSection={activeSection} />
        </div>
        <div className="canvas-layer mobile-canvas">
          <div className="canvas-wall-mobile" style={{ clipPath: seamClipMobile }} />
          <div className="canvas-wall-highlight-mobile" style={{ clipPath: seamClipSoftMobile }} />
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
          z-index: 30;
          overflow: hidden;
          pointer-events: auto;
          background: transparent;
          opacity: 1;
        }

        .desktop-canvas {
          right: 0;
          width: 40vw;
          top: 0;
          height: 100vh;
        }

        .mobile-canvas {
          display: none;
          bottom: 0;
          left: 0;
          width: 100%;
          height: 35vh;
          right: auto;
          top: auto;
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

        .canvas-wall-mobile {
          position: absolute;
          bottom: 0;
          left: 0;
          width: 100%;
          height: 60%;
          z-index: 26;
          pointer-events: none;
          background: linear-gradient(
            0deg,
            var(--seam-bg-solid) 0%,
            var(--seam-bg-solid) 58%,
            var(--seam-bg-soft) 78%,
            rgba(0, 0, 0, 0) 100%
          );
          transition: clip-path 520ms cubic-bezier(0.22, 1, 0.36, 1);
        }

        .canvas-wall-highlight-mobile {
          position: absolute;
          inset: auto 0 0 0;
          width: 100%;
          height: 60%;
          z-index: 27;
          pointer-events: none;
          background:
            radial-gradient(56px 30px at 8% 74%, rgba(255, 255, 255, 0.35), transparent 70%),
            radial-gradient(46px 28px at 32% 70%, rgba(255, 255, 255, 0.3), transparent 72%),
            radial-gradient(62px 34px at 58% 76%, rgba(255, 255, 255, 0.28), transparent 70%),
            radial-gradient(44px 28px at 84% 72%, rgba(255, 255, 255, 0.28), transparent 72%);
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
          display: flex;
          justify-content: center;
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
          width: 100% !important;
          max-width: 760px !important;
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
          .desktop-canvas {
            width: 38vw;
          }

          .content-wrapper {
            width: 82vw;
            background: transparent !important;
          }
        }

        @media (max-width: 1024px) {
          .desktop-canvas {
            display: none;
          }

          .mobile-canvas {
            display: block;
            height: 42vh;
          }

          .content-wrapper {
            width: 100%;
            background: transparent !important;
            border-right: none;
            padding-bottom: 40vh;
          }

          .mobile-canvas :global([class*="pagination"]) {
            display: none;
          }

          .content-wrapper :global(section)::before {
            z-index: 0;
          }

          .content-wrapper :global(section) {
            padding-inline: 1.5rem !important;
            width: 100%;
            text-align: center;
          }

          .content-wrapper :global(section > div) {
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 auto !important;
            display: flex;
            flex-direction: column;
            align-items: center;
          }

          .content-wrapper :global(.hero-actions),
          .content-wrapper :global(.hero-install) {
            justify-content: center;
            margin-left: auto;
            margin-right: auto;
          }

        }
      `}</style>
    </div>
  );
}
