/**
 * @fileoverview NeuralForest — Master R3F scene for the AetherWeave loom
 *
 * The primary Three.js scene composing all visual elements:
 *   - Ambient + directional lighting setup (cyber-organic palette)
 *   - Fog for depth (near 5, far 60)
 *   - Post-processing: Bloom pass for HDR glow (via @react-three/postprocessing)
 *   - ParticleField ambient cloud
 *   - All ArchNodeMesh instances (one per graph node)
 *   - All EdgeBeam instances (one per graph edge)
 *   - OrbitControls (touch + mouse drag, auto-rotate when idle)
 *   - Camera auto-fit when a new graph is loaded
 *
 * This component is rendered inside <Canvas> in LoomCanvas.
 * It reads the ArchGraph from the Zustand store directly so it
 * updates automatically as the WebSocket streams new generations.
 *
 * @module components/canvas/neural-forest
 */

"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Stars, Environment } from "@react-three/drei";
import * as THREE from "three";

import { useLoomStore } from "@/store/loom-store";
import { useNodePositions } from "@/hooks/use-node-positions";
import { useAnalytics } from "@/hooks/use-analytics";
import { ArchNodeMesh } from "@/components/canvas/arch-node-mesh";
import { EdgeBeam } from "@/components/canvas/edge-beam";
import { ParticleField } from "@/components/canvas/particle-field";
import { AnalyticsOverlay } from "@/components/canvas/analytics-overlay";

/* ─── Constants ──────────────────────────────────────────────────────────── */

/** Default camera position when no graph is loaded. */
const INITIAL_CAMERA = new THREE.Vector3(0, 0, 22);

/** Auto-rotate speed when idle (radians/second). */
const AUTO_ROTATE_SPEED = 0.15;

/* ─── CameraController ────────────────────────────────────────────────────── */

/**
 * CameraController — auto-fits the camera to the bounding box of all nodes
 * whenever a new graph is loaded (node count changes).
 *
 * @param nodeCount - Number of nodes in the current graph.
 */
function CameraController({ nodeCount }: { nodeCount: number }): null {
  const { camera } = useThree();
  const prevCount = useRef(0);

  useEffect(() => {
    if (nodeCount > 0 && nodeCount !== prevCount.current) {
      prevCount.current = nodeCount;
      // Pan back to see all nodes; simple heuristic based on count
      const dist = Math.max(18, Math.sqrt(nodeCount) * 5);
      camera.position.set(0, 0, dist);
      camera.lookAt(0, 0, 0);
    }
  }, [nodeCount, camera]);

  return null;
}

/* ─── NeuralForest ───────────────────────────────────────────────────────── */

/**
 * NeuralForest — the primary R3F scene rendered inside <Canvas>.
 *
 * Reads the Zustand store directly:
 *   - activeGraph      → node + edge data
 *   - evolutionStatus  → enables particle/beam boost
 *   - latestFitness    → drives accent colour
 *
 * @returns R3F JSX (must be rendered inside a <Canvas> context).
 */
export function NeuralForest(): React.JSX.Element {
  const activeGraph      = useLoomStore((s) => s.activeGraph);
  const evolutionStatus  = useLoomStore((s) => s.evolutionStatus);
  const latestFitness    = useLoomStore((s) => s.latestFitness);
  const activeGraphId    = useLoomStore((s) => s.activeGraphId);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [showAnalytics,  setShowAnalytics]  = useState(true);

  const evolutionActive = evolutionStatus === "running";

  const { nodes, edges, nodeMap } = useNodePositions(activeGraph);

  // Fetch Neo4j analytics (Redis-cached, 60s TTL)
  const { data: analytics } = useAnalytics(activeGraphId ?? null);

  /** Build a Map from node id → color for EdgeBeam lookups. */
  const nodeColorMap = new Map<string, string>(
    nodes.map((n) => [n.id, n.color])
  );

  /** Derive accent colour from aggregate fitness (green → violet gradient). */
  const accentColor = latestFitness
    ? `hsl(${Math.round(latestFitness.aggregate * 200 + 200)}, 80%, 60%)`
    : "#7c3aed";

  const handleNodeSelect = useCallback((id: string) => {
    setSelectedNodeId((prev) => (prev === id ? null : id));
  }, []);

  /** Click on canvas background → deselect. */
  const handlePointerMissed = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  return (
    <>
      {/* ── Camera controller ────────────────────────────────────────────── */}
      <CameraController nodeCount={nodes.length} />

      {/* ── Lighting ─────────────────────────────────────────────────────── */}
      <ambientLight intensity={0.15} color="#1a0533" />
      <directionalLight
        position={[10, 20, 10]}
        intensity={0.8}
        color="#c4b5fd"
        castShadow
      />
      <pointLight position={[-10, -10, -5]} intensity={0.4} color="#0ea5e9" />
      <pointLight position={[15, 5, 0]}    intensity={0.3} color="#a78bfa" />

      {/* ── Environment + Stars ───────────────────────────────────────────── */}
      <Stars
        radius={60}
        depth={30}
        count={2500}
        factor={3}
        saturation={0.8}
        fade
        speed={0.3}
      />

      {/* ── Fog for depth ────────────────────────────────────────────────── */}
      <fog attach="fog" args={["#07030f", 5, 60]} />

      {/* ── Particle field ────────────────────────────────────────────────── */}
      <ParticleField evolutionActive={evolutionActive} accentColor={accentColor} />

      {/* ── Architecture edges ───────────────────────────────────────────── */}
      {edges.map((edge) => (
        <EdgeBeam
          key={edge.id}
          edge={edge}
          sourceColor={nodeColorMap.get(
            Array.from(nodeMap.entries()).find(
              ([, v]) => v === edge.source
            )?.[0] ?? ""
          ) ?? "#7c3aed"}
          targetColor={nodeColorMap.get(
            Array.from(nodeMap.entries()).find(
              ([, v]) => v === edge.target
            )?.[0] ?? ""
          ) ?? "#0ea5e9"}
          evolutionActive={evolutionActive}
        />
      ))}

      {/* ── Architecture nodes ───────────────────────────────────────────── */}
      {nodes.map((node) => (
        <ArchNodeMesh
          key={node.id}
          node={node}
          isSelected={selectedNodeId === node.id}
          onSelect={handleNodeSelect}
          evolutionRing={evolutionActive}
        />
      ))}

      {/* ── Neo4j analytics overlay ──────────────────────────────────────── */}
      {analytics && showAnalytics && nodes.length > 0 && (
        <AnalyticsOverlay analytics={analytics} nodeMap={nodeMap} />
      )}

      {/* ── Empty state: floating prompt ─────────────────────────────────── */}
      {nodes.length === 0 && (
        <mesh position={[0, 0, 0]} onPointerMissed={handlePointerMissed}>
          <sphereGeometry args={[0.5, 16, 16]} />
          <meshStandardMaterial
            color="#7c3aed"
            emissive="#7c3aed"
            emissiveIntensity={1.2}
            transparent
            opacity={0.8}
          />
        </mesh>
      )}

      {/* ── Orbit controls ───────────────────────────────────────────────── */}
      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        autoRotate={!evolutionActive && nodes.length === 0}
        autoRotateSpeed={AUTO_ROTATE_SPEED}
        minDistance={3}
        maxDistance={60}
        enablePan
        makeDefault
      />
    </>
  );
}
