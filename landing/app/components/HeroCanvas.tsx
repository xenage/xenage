"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface HeroCanvasProps {
  activeSection: number;
}

const complexityBySection = [1, 1, 2, 2, 3, 4, 5, 6];

function createMobiusGeometry(detail: number): THREE.BufferGeometry {
  const segmentsU = 28 + detail * 16;
  const segmentsV = 100 + detail * 52;
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

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function createKnotGeometry(detail: number, scale = 1): THREE.BufferGeometry {
  const tubularSegments = 180 + detail * 90;
  const radialSegments = 14 + detail * 3;
  const radius = 1.18 + detail * 0.012;
  const tube = 0.07 + detail * 0.003;
  return new THREE.TorusKnotGeometry(
    radius * scale,
    tube * scale,
    tubularSegments,
    radialSegments,
    2 + Math.floor(detail * 0.5),
    3,
  );
}

export default function HeroCanvas({ activeSection }: HeroCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rootGroupRef = useRef<THREE.Group | null>(null);
  const mobiusRef = useRef<THREE.Mesh | null>(null);
  const knotARef = useRef<THREE.Mesh | null>(null);
  const knotBRef = useRef<THREE.Mesh | null>(null);
  const knotCRef = useRef<THREE.Mesh | null>(null);
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
      const oldGeometry = mobiusRef.current.geometry;
      const newGeometry = createMobiusGeometry(complexity);
      mobiusRef.current.geometry = newGeometry;
      oldGeometry.dispose();

      const mat = mobiusRef.current.material as THREE.MeshBasicMaterial;
      mat.color.copy(mobiusColor);
      mat.opacity = 0.44 + Math.min(0.32, complexity * 0.065);
    }

    if (knotARef.current) {
      const oldGeometry = knotARef.current.geometry;
      knotARef.current.geometry = createKnotGeometry(complexity, 1);
      oldGeometry.dispose();
      const mat = knotARef.current.material as THREE.MeshBasicMaterial;
      mat.color.copy(knotColor);
      mat.opacity = 0.42 + Math.min(0.24, complexity * 0.045);
    }

    if (knotBRef.current) {
      const oldGeometry = knotBRef.current.geometry;
      knotBRef.current.geometry = createKnotGeometry(Math.max(1, complexity - 1), 0.78);
      oldGeometry.dispose();
      knotBRef.current.visible = complexity >= 3;
      const mat = knotBRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.2 + Math.min(0.18, complexity * 0.03);
    }

    if (knotCRef.current) {
      const oldGeometry = knotCRef.current.geometry;
      knotCRef.current.geometry = createKnotGeometry(Math.max(1, complexity - 2), 0.56);
      oldGeometry.dispose();
      knotCRef.current.visible = complexity >= 5;
      const mat = knotCRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.14 + Math.min(0.14, complexity * 0.024);
    }

    if (particlesRef.current && particlesRef.current.material) {
      const mat = particlesRef.current.material as THREE.PointsMaterial;
      mat.size = 0.02 + Math.min(0.035, complexity * 0.0045);
      mat.opacity = 0.18 + Math.min(0.28, complexity * 0.048);
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
    knotARef.current = knotA;
    rootGroup.add(knotA);

    const knotB = new THREE.Mesh(
      createKnotGeometry(1, 0.78),
      new THREE.MeshBasicMaterial({
        color: 0xa3bcff,
        wireframe: true,
        transparent: true,
        opacity: 0.24,
      }),
    );
    knotB.position.x = 0.24;
    knotB.rotation.x = 0.8;
    knotBRef.current = knotB;
    rootGroup.add(knotB);

    const knotC = new THREE.Mesh(
      createKnotGeometry(1, 0.56),
      new THREE.MeshBasicMaterial({
        color: 0xc4cbff,
        wireframe: true,
        transparent: true,
        opacity: 0.2,
      }),
    );
    knotC.position.x = -0.27;
    knotC.rotation.y = 0.92;
    knotCRef.current = knotC;
    rootGroup.add(knotC);

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
    const animate = (time: number) => {
      animationId = requestAnimationFrame(animate);

      dragRef.current.x += (dragTargetRef.current.x - dragRef.current.x) * 0.09;
      dragRef.current.y += (dragTargetRef.current.y - dragRef.current.y) * 0.09;
      if (!draggingRef.current) {
        dragTargetRef.current.x *= 0.985;
        dragTargetRef.current.y *= 0.985;
      }

      if (rootGroupRef.current) {
        rootGroupRef.current.rotation.x +=
          0.0016 + mouseRef.current.y * 0.0007 + dragRef.current.y * 0.0028;
        rootGroupRef.current.rotation.y +=
          0.0024 + mouseRef.current.x * 0.0007 + dragRef.current.x * 0.0028;

        rootGroupRef.current.position.x +=
          (baseXOffset + mouseRef.current.x * 0.07 - rootGroupRef.current.position.x) * 0.028;
        const targetY =
          topCenterYOffset - scrollProgressRef.current * scrollYOffset - mouseRef.current.y * 0.03;
        rootGroupRef.current.position.y +=
          (targetY - rootGroupRef.current.position.y) * 0.028;
      }

      if (knotARef.current) {
        knotARef.current.rotation.x += 0.0012;
        knotARef.current.rotation.z += 0.0017;
      }
      if (knotBRef.current) {
        knotBRef.current.rotation.y -= 0.0015;
      }
      if (knotCRef.current) {
        knotCRef.current.rotation.x += 0.0019;
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
      if (knotBRef.current) {
        knotBRef.current.geometry.dispose();
        (knotBRef.current.material as THREE.MeshBasicMaterial).dispose();
      }
      if (knotCRef.current) {
        knotCRef.current.geometry.dispose();
        (knotCRef.current.material as THREE.MeshBasicMaterial).dispose();
      }
      particleGeometry.dispose();
      particleMaterial.dispose();
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    if (activeSection === lastSectionRef.current) return;
    lastSectionRef.current = activeSection;
    const complexity =
      complexityBySection[activeSection] ?? complexityBySection[complexityBySection.length - 1];
    applyComplexity(complexity);
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
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
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
    </div>
  );
}
