"use client";

import Image from "next/image";
import Link from "next/link";

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer
      style={{
        width: "100%",
        background: "rgba(255, 255, 255, 0.96)",
        borderTop: "1px solid rgba(0, 0, 0, 0.08)",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "4rem 2rem 2rem",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "3rem",
            marginBottom: "3rem",
            flexWrap: "wrap",
          }}
        >
          <div>
            <Link
              href="/"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                textDecoration: "none",
                marginBottom: "1rem",
              }}
            >
              <div
                style={{
                  width: "28px",
                  height: "28px",
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
                  fontSize: "1.1rem",
                  letterSpacing: "-0.02em",
                  color: "#0d0d0d",
                }}
              >
                xenage
              </span>
            </Link>
            <p
              style={{
                fontFamily: "Space Grotesk, sans-serif",
                fontSize: "0.85rem",
                color: "#4a4a4a",
                margin: 0,
                maxWidth: "200px",
              }}
            >
              Agent orchestration for teams who ship.
            </p>
          </div>

          <div
            style={{
              display: "flex",
              gap: "4rem",
            }}
          >
            <div>
              <h4
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "#0d0d0d",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: "1rem",
                }}
              >
                Product
              </h4>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <a
                  href="#features"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  Features
                </a>
                <a
                  href="#install"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  Install
                </a>
                <a
                  href="#scale"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  Scale
                </a>
                <a
                  href="#gui"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  GUI
                </a>
              </div>
            </div>

            <div>
              <h4
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "#0d0d0d",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: "1rem",
                }}
              >
                Resources
              </h4>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <a
                  href="https://docs.xenage.dev"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  Documentation
                </a>
                <a
                  href="https://github.com/xenage"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  GitHub
                </a>
              </div>
            </div>

            <div>
              <h4
                style={{
                  fontFamily: "Space Grotesk, sans-serif",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "#0d0d0d",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: "1rem",
                }}
              >
                Company
              </h4>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <a
                  href="https://docs.xenage.dev"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  About
                </a>
                <a
                  href="https://github.com/xenage/xenage/releases"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontFamily: "Space Grotesk, sans-serif",
                    fontSize: "0.85rem",
                    color: "#4a4a4a",
                    textDecoration: "none",
                    transition: "color 0.2s ease",
                  }}
                >
                  Blog
                </a>
              </div>
            </div>
          </div>
        </div>

        <div
          style={{
            width: "100%",
            height: "1px",
            background:
              "linear-gradient(90deg, transparent, rgba(0, 102, 255, 0.2), transparent)",
            marginBottom: "1.5rem",
          }}
        />

        <p
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "0.8rem",
            color: "#8a8a8a",
            textAlign: "center",
            margin: 0,
          }}
        >
          © {currentYear} Xenage. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
