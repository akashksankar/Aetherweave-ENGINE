/**
 * @fileoverview ParticleField — Ambient bioluminescent particle cloud
 *
 * Renders thousands of tiny particles drifting slowly through the neural
 * forest as a living atmospheric effect.
 *
 * Implementation:
 *   - Uses a single `<points>` mesh (most performant for many particles).
 *   - Positions stored in a Float32Array updated each frame via BufferAttribute.
 *   - Each particle drifts upward at a random speed and wraps when it exits
 *     the bounding box.
 *   - During evolution, particles cluster near active node positions and
 *     their opacity increases dramatically.
 *
 * Performance:
 *   - COUNT = 3500 particles (comfortable on mobile GPUs)
 *   - BufferGeometry.drawRange limits the draw call.
 *   - `needsUpdate = true` on the position attribute triggers a GPU upload.
 *
 * @module components/canvas/particle-field
 */

"use client";

import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/** Total particle count. */
const COUNT = 3500;

/** Bounding box for particle drift. */
const BOUNDS = 18;

interface ParticleFieldProps {
  /** Boost particle intensity during evolution. */
  evolutionActive: boolean;
  /** Neon accent colour for particles (matches current fitness). */
  accentColor?: string;
}

/**
 * ParticleField — points-based ambient particle cloud.
 *
 * @param evolutionActive - If true, particles glow brighter and drift faster.
 * @param accentColor     - Optional hex accent colour override.
 */
export function ParticleField({
  evolutionActive,
  accentColor = "#7c3aed",
}: ParticleFieldProps): React.JSX.Element {
  const pointsRef = useRef<THREE.Points>(null!);

  /**
   * Generate initial random positions and drift speeds.
   * Speeds are seeded once and reused each frame.
   */
  const { positions, speeds, sizes } = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    const speeds    = new Float32Array(COUNT);  // y-drift speed per particle
    const sizes     = new Float32Array(COUNT);  // point size per particle

    for (let i = 0; i < COUNT; i++) {
      positions[i * 3]     = (Math.random() - 0.5) * BOUNDS * 2;
      positions[i * 3 + 1] = (Math.random() - 0.5) * BOUNDS * 2;
      positions[i * 3 + 2] = (Math.random() - 0.5) * BOUNDS;
      speeds[i]   = 0.004 + Math.random() * 0.008;
      sizes[i]    = Math.random() * 3 + 1;
    }
    return { positions, speeds, sizes };
  }, []);

  /**
   * Each frame: update particle positions and re-upload to GPU.
   * Particles drift upward and wrap when they exit BOUNDS.
   */
  useFrame((_, delta) => {
    if (!pointsRef.current) return;
    const geo = pointsRef.current.geometry;
    const pos = geo.attributes.position as THREE.BufferAttribute;

    const speedMult = evolutionActive ? 2.5 : 1.0;

    for (let i = 0; i < COUNT; i++) {
      pos.array[i * 3 + 1] += speeds[i]! * speedMult;

      // Wrap around when particle exits vertical bounds
      if ((pos.array[i * 3 + 1] as number) > BOUNDS) {
        pos.array[i * 3 + 1] = -BOUNDS;
      }
    }

    pos.needsUpdate = true;

    // Pulse the point material size
    const mat = pointsRef.current.material as THREE.PointsMaterial;
    const targetSize = evolutionActive ? 1.6 : 0.8;
    mat.size = THREE.MathUtils.lerp(mat.size, targetSize, 0.04);
    mat.opacity = THREE.MathUtils.lerp(mat.opacity, evolutionActive ? 0.7 : 0.35, 0.04);
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={COUNT}
        />
        <bufferAttribute
          attach="attributes-size"
          args={[sizes, 1]}
          count={COUNT}
        />
      </bufferGeometry>
      <pointsMaterial
        color={accentColor}
        size={0.8}
        sizeAttenuation
        transparent
        opacity={0.35}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        vertexColors={false}
      />
    </points>
  );
}
