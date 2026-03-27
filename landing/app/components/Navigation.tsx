"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { Github, Menu, X } from "lucide-react";

function XSocialIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.847h-7.406l-5.8-7.584-6.64 7.584H.47l8.6-9.83L0 1.154h7.594l5.243 6.932 6.064-6.933Zm-1.3 19.477h2.04L6.477 3.133H4.29L17.6 20.63Z" />
    </svg>
  );
}

export default function Navigation() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      aria-label="Primary"
      className={`nav ${isScrolled ? "nav-scrolled" : ""}`}
      style={{
        width: "100%",
        padding: "1.5rem 0",
        transition: "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 2rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Link
          href="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            textDecoration: "none",
          }}
        >
          <div
            style={{
              width: "32px",
              height: "32px",
              position: "relative",
            }}
          >
            <Image
              src="/xenage.png"
              alt="Xenage"
              fill
              style={{ objectFit: "contain" }}
            />
          </div>
          <span
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontWeight: 700,
              fontSize: "1.25rem",
              letterSpacing: "-0.02em",
              color: "#0d0d0d",
            }}
          >
            xenage
          </span>
        </Link>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "2rem",
          }}
          className="nav-links"
        >
          <a
            href="#problems"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              color: "#4a4a4a",
              textDecoration: "none",
              transition: "color 0.3s ease",
            }}
          >
            Why
          </a>
          <a
            href="#features"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              color: "#4a4a4a",
              textDecoration: "none",
              transition: "color 0.3s ease",
            }}
          >
            Features
          </a>
          <a
            href="#install"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              color: "#4a4a4a",
              textDecoration: "none",
              transition: "color 0.3s ease",
            }}
          >
            Install
          </a>
          <a
            href="#scale"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              color: "#4a4a4a",
              textDecoration: "none",
              transition: "color 0.3s ease",
            }}
          >
            Scale
          </a>
          <a
            href="#gui"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.9rem",
              fontWeight: 500,
              color: "#4a4a4a",
              textDecoration: "none",
              transition: "color 0.3s ease",
            }}
          >
            GUI
          </a>
          <a
            href="#install"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.85rem",
              fontWeight: 500,
              padding: "0.6rem 1.25rem",
              background: "linear-gradient(135deg, #0066ff 0%, #0a7dff 100%)",
              border: "none",
              color: "#fafafa",
              cursor: "pointer",
              borderRadius: "8px",
              transition: "all 0.3s ease",
              textDecoration: "none",
            }}
          >
            Get Started
          </a>
          <div className="nav-socials">
            <a
              href="https://github.com/xenage"
              target="_blank"
              rel="noreferrer"
              className="social-link"
              aria-label="Xenage on GitHub"
              title="GitHub"
            >
              <Github size={17} />
            </a>
            <a
              href="https://x.com/xenage_dev"
              target="_blank"
              rel="noreferrer"
              className="social-link social-link--x"
              aria-label="Xenage on X.com"
              title="X.com"
            >
              <XSocialIcon />
            </a>
          </div>
        </div>

        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          style={{
            display: "none",
            background: "transparent",
            border: "none",
            color: "#0d0d0d",
            cursor: "pointer",
          }}
          className="mobile-menu-btn"
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {mobileMenuOpen && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            padding: "1rem 2rem",
            background: "rgba(255, 255, 255, 0.98)",
            borderTop: "1px solid rgba(0, 0, 0, 0.06)",
          }}
          className="mobile-menu"
        >
          <a
            href="#problems"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "1rem",
              color: "#4a4a4a",
              textDecoration: "none",
            }}
          >
            Why
          </a>
          <a
            href="#features"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "1rem",
              color: "#4a4a4a",
              textDecoration: "none",
            }}
          >
            Features
          </a>
          <a
            href="#install"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "1rem",
              color: "#4a4a4a",
              textDecoration: "none",
            }}
          >
            Install
          </a>
          <a
            href="#scale"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "1rem",
              color: "#4a4a4a",
              textDecoration: "none",
            }}
          >
            Scale
          </a>
          <a
            href="#gui"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "1rem",
              color: "#4a4a4a",
              textDecoration: "none",
            }}
          >
            GUI
          </a>
          <a
            href="#install"
            style={{
              fontFamily: "Space Grotesk, sans-serif",
              fontSize: "0.85rem",
              fontWeight: 500,
              padding: "0.6rem 1.2rem",
              background: "linear-gradient(135deg, #0066ff 0%, #0a7dff 100%)",
              border: "none",
              color: "#fafafa",
              cursor: "pointer",
              borderRadius: "8px",
              textDecoration: "none",
            }}
          >
            Get Started
          </a>
          <div className="mobile-socials">
            <a
              href="https://github.com/xenage"
              target="_blank"
              rel="noreferrer"
              className="social-link"
              aria-label="Xenage on GitHub"
            >
              <Github size={18} />
              GitHub
            </a>
            <a
              href="https://x.com/xenage_dev"
              target="_blank"
              rel="noreferrer"
              className="social-link social-link--x"
              aria-label="Xenage on X.com"
            >
              <XSocialIcon />
              X.com
            </a>
          </div>
        </div>
      )}

      <style jsx>{`
        .nav {
          position: sticky;
          top: 0;
          z-index: 100;
          background: rgba(255, 255, 255, 0.85);
          backdrop-filter: blur(12px);
          border-bottom: 1px solid rgba(0, 0, 0, 0.04);
        }
        .nav-scrolled {
          background: rgba(255, 255, 255, 0.95) !important;
          backdrop-filter: blur(20px);
          padding: 1rem 0 !important;
          box-shadow: 0 1px 0 rgba(0, 0, 0, 0.08);
          border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        }
        .nav-socials {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          margin-left: 0.25rem;
        }
        .social-link {
          width: 34px;
          height: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 10px;
          text-decoration: none;
          color: #212121;
          background: rgba(255, 255, 255, 0.9);
          border: 1px solid rgba(0, 0, 0, 0.08);
          transition: all 0.24s ease;
          box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
        }
        .social-link :global(svg) {
          width: 17px;
          height: 17px;
        }
        .social-link:hover {
          color: #fafafa;
          background: linear-gradient(135deg, #0066ff 0%, #0a7dff 100%);
          border-color: transparent;
          transform: translateY(-2px);
          box-shadow: 0 12px 24px rgba(0, 102, 255, 0.28);
        }
        .social-link--x :global(svg) {
          width: 15px;
          height: 15px;
        }
        .mobile-socials {
          display: flex;
          gap: 0.75rem;
          padding-top: 0.35rem;
        }
        .mobile-socials .social-link {
          width: auto;
          height: auto;
          padding: 0.45rem 0.75rem;
          gap: 0.45rem;
          border-radius: 999px;
          font-family: "Space Grotesk", sans-serif;
          font-size: 0.9rem;
        }
        .mobile-socials .social-link :global(svg) {
          width: 16px;
          height: 16px;
        }
        @media (max-width: 768px) {
          .nav-links {
            display: none !important;
          }
          .mobile-menu-btn {
            display: block !important;
          }
          .mobile-menu {
            display: flex !important;
          }
        }
      `}</style>
    </nav>
  );
}
