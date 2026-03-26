/**
 * @fileoverview ArchNodeMesh — 3D mesh for a single architecture node
 *
 * Each node in the neural forest is rendered as an icosahedron with:
 *   - Bioluminescent emissive colour (per node type)
 *   - A glowing halo ring (torus with additive blending)
 *   - Framer-3D spring animation on position changes (lerp each frame)
 *   - Hover → scale up + brighter emissive intensity
 *   - Click → select node and surface info in the sidebar
 *   - "Pulse" animation driven by the node's fitness value
 *
 * Rendering approach:
 *   - Uses `useRef` for the mesh and lerps its position each frame
 *     in `useFrame()` for butter-smooth animation without re-renders.
 *   - Emissive intensity pulses using a sine wave tied to the clock.
 *
 * @module components/canvas/arch-node-mesh
 */

"use client";

import React, { useRef, useState, useCallback } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard, Text } from "@react-three/drei";
import * as THREE from "three";
import type { NodePosition } from "@/hooks/use-node-positions";

/* ─── Constants ──────────────────────────────────────────────────────────── */

/** Camera lerp speed: 1 = snap, 0 = never moves. */
const LERP_SPEED = 0.08;

/** Maximum emissive intensity at rest. */
const BASE_EMISSIVE = 0.6;

/** Emissive intensity when hovered. */
const HOVER_EMISSIVE = 2.0;

/** Pulse amplitude on top of BASE_EMISSIVE. */
const PULSE_AMPLITUDE = 0.25;

/** How quickly the node pops to scale on hover. */
const HOVER_SCALE = 1.35;

interface ArchNodeMeshProps {
  node: NodePosition;
  isSelected: boolean;
  onSelect: (id: string) => void;
  evolutionRing?: boolean; // Show animated ring during evolution
}

/**
 * ArchNodeMesh — animated, interactive 3D node sphere.
 *
 * @param node          - NodePosition data from useNodePositions.
 * @param isSelected    - Whether this node is currently selected.
 * @param onSelect      - Callback when the node is clicked.
 * @param evolutionRing - Show the animated evolution ring if true.
 */
export function ArchNodeMesh({
  node,
  isSelected,
  onSelect,
  evolutionRing = false,
}: ArchNodeMeshProps): React.JSX.Element {
  const meshRef     = useRef<THREE.Mesh>(null!);
  const ringRef     = useRef<THREE.Mesh>(null!);
  const matRef      = useRef<THREE.MeshStandardMaterial>(null!);
  const currentPos  = useRef(node.position.clone());
  const [hovered, setHovered] = useState(false);

  const colorObj = new THREE.Color(node.color);

  /** Each frame: lerp position + pulse emissive + spin ring. */
  useFrame((state) => {
    const { clock } = state;
    const t = clock.getElapsedTime();

    // Smooth position lerp (avoids jarring jumps when graph updates)
    currentPos.current.lerp(node.position, LERP_SPEED);
    if (meshRef.current) {
      meshRef.current.position.copy(currentPos.current);
    }

    // Emissive pulse based on fitness (higher fitness = faster pulse)
    if (matRef.current) {
      const pulseFreq  = 0.5 + node.fitness * 1.5;
      const pulse = Math.sin(t * pulseFreq * Math.PI) * PULSE_AMPLITUDE;
      const target = hovered
        ? HOVER_EMISSIVE
        : BASE_EMISSIVE + pulse + (isSelected ? 0.8 : 0);
      matRef.current.emissiveIntensity = THREE.MathUtils.lerp(
        matRef.current.emissiveIntensity,
        target,
        0.12
      );
    }

    // Hover scale lerp
    if (meshRef.current) {
      const targetScale = hovered || isSelected ? HOVER_SCALE : 1;
      meshRef.current.scale.lerp(
        new THREE.Vector3(targetScale, targetScale, targetScale),
        0.15
      );
    }

    // Spin the evolution ring
    if (ringRef.current && evolutionRing) {
      ringRef.current.rotation.z = t * 1.2;
      ringRef.current.rotation.x = Math.sin(t * 0.4) * 0.5;
    }
  });

  const handleClick = useCallback(
    (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      onSelect(node.id);
    },
    [node.id, onSelect]
  );

  return (
    <group>
      {/* ── Main node sphere ────────────────────────────────────────────── */}
      <mesh
        ref={meshRef}
        position={node.position}
        onClick={handleClick}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true);  }}
        onPointerOut={() => setHovered(false)}
        castShadow
        receiveShadow
      >
        <icosahedronGeometry args={[node.size, 1]} />
        <meshStandardMaterial
          ref={matRef}
          color={colorObj}
          emissive={colorObj}
          emissiveIntensity={BASE_EMISSIVE}
          metalness={0.2}
          roughness={0.3}
          transparent
          opacity={0.92}
        />
      </mesh>

      {/* ── Selection / evolution ring ───────────────────────────────────── */}
      {(isSelected || evolutionRing) && (
        <mesh ref={ringRef} position={node.position}>
          <torusGeometry args={[node.size * 1.6, 0.04, 8, 32]} />
          <meshBasicMaterial
            color={evolutionRing ? "#a78bfa" : node.color}
            transparent
            opacity={evolutionRing ? 0.9 : 0.7}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      )}

      {/* ── Glow halo (large transparent disc) ──────────────────────────── */}
      <mesh position={node.position}>
        <sphereGeometry args={[node.size * 2.2, 8, 8]} />
        <meshBasicMaterial
          color={node.color}
          transparent
          opacity={0.04}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>

      {/* ── Floating label (Billboard — always faces camera) ────────────── */}
      {(hovered || isSelected) && (
        <Billboard position={[
          node.position.x,
          node.position.y + node.size + 0.35,
          node.position.z,
        ]}>
          <Text
            fontSize={0.22}
            color="#e2d9f3"
            anchorX="center"
            anchorY="bottom"
            font="/fonts/JetBrainsMono-Regular.ttf"
            outlineWidth={0.015}
            outlineColor="#000000"
          >
            {node.label}
            {"\n"}
            <Text
              fontSize={0.16}
              color={node.color}
            >
              {node.type} · {(node.fitness * 100).toFixed(0)}%
            </Text>
          </Text>
        </Billboard>
      )}
    </group>
  );
}
