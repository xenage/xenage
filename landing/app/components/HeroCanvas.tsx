"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface HeroCanvasProps {
  activeSection: number;
}

const complexityBySection = [1, 1, 2, 2, 3, 4, 5, 6];

function createMobiusGeometry(detail: number, geometry?: THREE.BufferGeometry): THREE.BufferGeometry {
  const segmentsU = 124;
  const segmentsV = 412;
  const width = 0.34 + detail * 0.02;
  const radius = 1.45;

  const positions: number[] = [];
  const indices: number[] = [];

  for (let iu = 0; iu <= segmentsU; iu += 1) {
    const u = (iu / segmentsU) * 2 - 1;
    for (let iv = 0; iv <= segmentsV; iv += 1) {
      const v = (iv / segmentsV) * Math.PI * 2;
      const t = u * width;

      const x = (radius + t * Math.cos(v * 0.5)) * Math.cos(v);
      const y = (radius + t * Math.cos(v * 0.5)) * Math.sin(v);
      const z = t * Math.sin(v * 0.5);

      positions.push(x, z * 1.35, y);
    }
  }

  if (geometry) {
    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    (posAttr.array as Float32Array).set(positions);
    posAttr.needsUpdate = true;
    geometry.computeVertexNormals();
    return geometry;
  }

  const row = segmentsV + 1;
  for (let iu = 0; iu < segmentsU; iu += 1) {
    for (let iv = 0; iv < segmentsV; iv += 1) {
      const a = iu * row + iv;
      const b = (iu + 1) * row + iv;
      const c = (iu + 1) * row + iv + 1;
      const d = iu * row + iv + 1;
      indices.push(a, b, d, b, c, d);
    }
  }

  const newGeometry = new THREE.BufferGeometry();
  newGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  newGeometry.setIndex(indices);
  newGeometry.computeVertexNormals();
  return newGeometry;
}

function createKnotGeometry(detail: number, scale = 1, geometry?: THREE.BufferGeometry): THREE.BufferGeometry {
  const tubularSegments = 720;
  const radialSegments = 32;
  const radius = 1.18 + detail * 0.01;
  const tube = 0.07 + detail * 0.002;
  const p = 2; // Упрощенный узел
  const q = 3;

  if (geometry) {
    const tempGeometry = new THREE.TorusKnotGeometry(
      radius * scale,
      tube * scale,
      tubularSegments,
      radialSegments,
      p,
      q,
    );
    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const tempPosAttr = tempGeometry.getAttribute("position") as THREE.BufferAttribute;
    (posAttr.array as Float32Array).set(tempPosAttr.array);
    posAttr.needsUpdate = true;
    geometry.computeVertexNormals();
    tempGeometry.dispose();
    return geometry;
  }

  return new THREE.TorusKnotGeometry(
    radius * scale,
    tube * scale,
    tubularSegments,
    radialSegments,
    p,
    q,
  );
}

export default function HeroCanvas({ activeSection }: HeroCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rootGroupRef = useRef<THREE.Group | null>(null);
  const mobiusRef = useRef<THREE.Mesh | null>(null);
  const knotARef = useRef<THREE.Mesh | null>(null);
  const particlesRef = useRef<THREE.Points | null>(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const dragRef = useRef({ x: 0, y: 0 });
  const dragTargetRef = useRef({ x: 0, y: 0 });
  const draggingRef = useRef(false);
  const scrollProgressRef = useRef(0);
  const zoomRef = useRef(3.85);
  const targetZoomRef = useRef(3.85);
  const lastSectionRef = useRef(-1);

  const baseXOffset = -0.14;
  const topCenterYOffset = 0.42;
  const scrollYOffset = 1.1;

  const applyComplexity = (complexity: number) => {
    const mobiusColor = new THREE.Color(0x92bbff);
    const knotColor = new THREE.Color(0x7dd5ff);

    if (mobiusRef.current) {
      createMobiusGeometry(complexity, mobiusRef.current.geometry);
      const mat = mobiusRef.current.material as THREE.MeshBasicMaterial;
      mat.color.copy(mobiusColor);
      mat.opacity = 0.44 + Math.min(0.32, complexity * 0.08);
    }

    if (knotARef.current) {
      createKnotGeometry(complexity, 1, knotARef.current.geometry);
      const mat = knotARef.current.material as THREE.MeshBasicMaterial;
      mat.color.copy(knotColor);
      mat.opacity = 0.42 + Math.min(0.24, complexity * 0.06);
    }

    if (particlesRef.current && particlesRef.current.material) {
      const mat = particlesRef.current.material as THREE.PointsMaterial;
      mat.size = 0.02 + Math.min(0.035, complexity * 0.005);
      mat.opacity = 0.18 + Math.min(0.28, complexity * 0.06);
    }
  };

  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
      56,
      container.clientWidth / container.clientHeight,
      0.1,
      1000,
    );
    camera.position.z = zoomRef.current;
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      alpha: true,
      antialias: true,
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const rootGroup = new THREE.Group();
    rootGroupRef.current = rootGroup;
    scene.add(rootGroup);

    const mobius = new THREE.Mesh(
      createMobiusGeometry(1),
      new THREE.MeshBasicMaterial({
        color: 0x92bbff,
        wireframe: true,
        transparent: true,
        opacity: 0.52,
      }),
    );
    mobius.geometry.setDrawRange(0, Infinity);
    mobiusRef.current = mobius;
    rootGroup.add(mobius);

    const knotA = new THREE.Mesh(
      createKnotGeometry(1, 1),
      new THREE.MeshBasicMaterial({
        color: 0x7dd5ff,
        wireframe: true,
        transparent: true,
        opacity: 0.45,
      }),
    );
    knotA.geometry.setDrawRange(0, Infinity);
    knotARef.current = knotA;
    rootGroup.add(knotA);

    const particleCount = 220;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i += 1) {
      const r = 2.4 + Math.random() * 2.4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const particleMaterial = new THREE.PointsMaterial({
      color: 0x9bd7ff,
      size: 0.028,
      transparent: true,
      opacity: 0.24,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    particlesRef.current = particles;
    rootGroup.add(particles);

    const handlePointerDown = () => {
      draggingRef.current = true;
      container.style.cursor = "grabbing";
    };

    const handlePointerMove = (e: PointerEvent) => {
      if (!draggingRef.current) return;
      dragTargetRef.current.x = THREE.MathUtils.clamp(
        dragTargetRef.current.x + e.movementX * 0.004,
        -1.35,
        1.35,
      );
      dragTargetRef.current.y = THREE.MathUtils.clamp(
        dragTargetRef.current.y + e.movementY * 0.004,
        -1.2,
        1.2,
      );
    };

    const handlePointerUp = () => {
      draggingRef.current = false;
      container.style.cursor = "grab";
    };

    const handleWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) {
        return;
      }
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      if (x < rect.width * 0.5) {
        return;
      }
      e.preventDefault();
      targetZoomRef.current = THREE.MathUtils.clamp(
        targetZoomRef.current + e.deltaY * 0.003,
        3.2,
        5.6,
      );
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };

    const handleScroll = () => {
      const scrollHeight = Math.max(
        1,
        document.documentElement.scrollHeight - window.innerHeight,
      );
      scrollProgressRef.current = window.scrollY / scrollHeight;
    };

    container.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    container.addEventListener("wheel", handleWheel, { passive: false });
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("scroll", handleScroll, { passive: true });

    const handleResize = () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    let animationId: number;
    let lastComplexity = -1;

    const animate = (time: number) => {
      animationId = requestAnimationFrame(animate);

      const targetComplexity = 1 + scrollProgressRef.current * 1.5;
      const currentComplexity = lastComplexity === -1 ? targetComplexity : lastComplexity + (targetComplexity - lastComplexity) * 0.05;

      if (Math.abs(currentComplexity - lastComplexity) > 0.001) {
        applyComplexity(currentComplexity);
        lastComplexity = currentComplexity;
      }

      dragRef.current.x += (dragTargetRef.current.x - dragRef.current.x) * 0.09;
      dragRef.current.y += (dragTargetRef.current.y - dragRef.current.y) * 0.09;
      if (!draggingRef.current) {
        dragTargetRef.current.x *= 0.985;
        dragTargetRef.current.y *= 0.985;
      }

      if (rootGroupRef.current) {
        const isMobile = window.innerWidth <= 1024;
        const currentBaseXOffset = isMobile ? 0 : baseXOffset;
        const currentTopCenterYOffset = isMobile ? -0.32 : topCenterYOffset;
        const currentScrollYOffset = isMobile ? 0 : scrollYOffset;

        rootGroupRef.current.rotation.x +=
          0.0016 + mouseRef.current.y * 0.0007 + dragRef.current.y * 0.0028;
        rootGroupRef.current.rotation.y +=
          0.0024 + mouseRef.current.x * 0.0007 + dragRef.current.x * 0.0028;

        rootGroupRef.current.position.x +=
          (currentBaseXOffset + mouseRef.current.x * 0.07 - rootGroupRef.current.position.x) * 0.028;
        const targetY =
          currentTopCenterYOffset - scrollProgressRef.current * currentScrollYOffset - mouseRef.current.y * 0.03;
        rootGroupRef.current.position.y +=
          (targetY - rootGroupRef.current.position.y) * 0.028;
      }

      if (knotARef.current) {
        knotARef.current.rotation.x += 0.0012;
        knotARef.current.rotation.z += 0.0017;
      }
      if (particlesRef.current) {
        particlesRef.current.rotation.y += 0.0006;
      }

      if (cameraRef.current) {
        zoomRef.current += (targetZoomRef.current - zoomRef.current) * 0.08;
        cameraRef.current.position.z = zoomRef.current;
      }

      renderer.render(scene, camera);
    };

    applyComplexity(1);
    handleScroll();
    animate(0);

    return () => {
      cancelAnimationFrame(animationId);
      container.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      container.removeEventListener("wheel", handleWheel);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", handleResize);

      if (mobiusRef.current) {
        mobiusRef.current.geometry.dispose();
        (mobiusRef.current.material as THREE.MeshBasicMaterial).dispose();
      }
      if (knotARef.current) {
        knotARef.current.geometry.dispose();
        (knotARef.current.material as THREE.MeshBasicMaterial).dispose();
      }
      particleGeometry.dispose();
      particleMaterial.dispose();
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    // We no longer call applyComplexity here as it's handled in animate loop
    lastSectionRef.current = activeSection;
  }, [activeSection]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        cursor: "grab",
      }}
    >
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background:
            "radial-gradient(circle at 74% 14%, rgba(136, 197, 255, 0.18), transparent 42%), radial-gradient(circle at 64% 78%, rgba(155, 164, 255, 0.16), transparent 48%)",
        }}
      />
      <div
        className="pagination-dots"
        style={{
          position: "absolute",
          right: "1.2rem",
          top: "50%",
          transform: "translateY(-50%)",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          pointerEvents: "none",
        }}
      >
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            style={{
              width: activeSection === i ? "10px" : "6px",
              height: activeSection === i ? "10px" : "6px",
              borderRadius: "50%",
              background: activeSection === i ? "#4f8eff" : "rgba(79,142,255,0.28)",
              transition: "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
          />
        ))}
      </div>
      <style jsx>{`
        @media (max-width: 1024px) {
          .pagination-dots {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
