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
import CtaSection from "./components/CtaSection";
import Footer from "./components/Footer";

gsap.registerPlugin(ScrollTrigger);

export default function Home() {
  const [activeSection, setActiveSection] = useState(0);
  const seamClip = "polygon(0% 0%, 76% 0%, 75.5% 12%, 76.8% 24%, 74.2% 38%, 76.2% 52%, 73.8% 66%, 75.6% 82%, 72% 100%, 0% 100%)";
  const seamClipSoft = "polygon(0% 0%, 81% 0%, 80.5% 14%, 81.8% 28%, 79.2% 42%, 81.2% 56%, 78.8% 70%, 80.6% 86%, 77% 100%, 0% 100%)";

  const seamClipMobile = "polygon(0% 100%, 100% 100%, 100% 24%, 86% 23.5%, 72% 25.2%, 58% 23.8%, 44% 24.8%, 30% 23.2%, 16% 25.5%, 0% 28%)";
  const seamClipSoftMobile = "polygon(0% 100%, 100% 100%, 100% 19%, 86% 18.5%, 72% 20.2%, 58% 18.8%, 44% 19.8%, 30% 18.2%, 16% 20.5%, 0% 23%)";
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        name: "Xenage",
        applicationCategory: "DeveloperApplication",
        operatingSystem: "Linux, macOS, Windows",
        url: "https://xenage.dev/",
        description:
          "Xenage is an agent orchestration platform to run, control, and observe AI agents across clusters.",
        brand: {
          "@type": "Brand",
          name: "Xenage",
        },
        sameAs: ["https://github.com/xenage", "https://docs.xenage.dev"],
      },
      {
        "@type": "Organization",
        name: "Xenage",
        url: "https://xenage.dev/",
        logo: "https://xenage.dev/xenage.png",
        sameAs: ["https://github.com/xenage", "https://docs.xenage.dev"],
      },
      {
        "@type": "WebSite",
        name: "Xenage",
        url: "https://xenage.dev/",
      },
    ],
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


  return (
    <div className="page-wrapper">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
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
        <main className="content-wrapper">
          <HeroSection />
          <ProblemsSection />
          <InstallSection />
          <FeaturesSection />
          <ScaleSection />
          <GuiSection />
          <CtaSection />
        </main>
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
        .content-wrapper :global(.gui-grid) {
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
