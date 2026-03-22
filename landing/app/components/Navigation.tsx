"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { Menu, X } from "lucide-react";

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
            gap: "2.5rem",
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
          <button
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
            }}
          >
            Get Started
          </button>
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
          <button
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
            }}
          >
            Get Started
          </button>
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
