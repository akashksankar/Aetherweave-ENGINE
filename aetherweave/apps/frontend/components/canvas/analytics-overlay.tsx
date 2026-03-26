/**
 * @fileoverview AnalyticsOverlay — R3F 3D analytics visualisation layer
 *
 * Renders Neo4j analytics results as visual overlays directly inside
 * the NeuralForest 3D scene:
 *
 *   Bottlenecks — pulsing red warning rings around SPOF nodes
 *   Hubs        — large amber halos around over-connected nodes
 *   Critical Path — bright white glow tube connecting path nodes
 *   Clusters    — subtle coloured ground-plane discs per cluster
 *
 * This component is a pure R3F scene child (must be inside <Canvas>).
 * It reads analytics data from props (passed from NeuralForest which
 * reads from React Query).
 *
 * @module components/canvas/analytics-overlay
 */

"use client";

import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard, Text } from "@react-three/drei";
import * as THREE from "three";
import type { AnalyticsResult } from "@/hooks/use-analytics";

/* ─── Cluster colour palette ─────────────────────────────────────────────── */

const CLUSTER_COLORS = [
  "#7c3aed", "#0ea5e9", "#10b981",
  "#f59e0b", "#ec4899", "#6366f1",
  "#8b5cf6", "#14b8a6",
];

/* ─── BottleneckMarker ───────────────────────────────────────────────────── */

interface BottleneckMarkerProps {
  position: THREE.Vector3;
  severity: number;
  label:    string;
}

/**
 * Animated red warning ring for SPOF bottleneck nodes.
 *
 * Scales in and out on a sin wave to draw attention.
 */
function BottleneckMarker({
  position, severity, label,
}: BottleneckMarkerProps): React.JSX.Element {
  const ringRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    if (!ringRef.current) return;
    const t = clock.getElapsedTime();
    const s = 1 + Math.sin(t * 3) * 0.15 * severity;
    ringRef.current.scale.setScalar(s);
    (ringRef.current.material as THREE.MeshBasicMaterial).opacity =
      0.4 + Math.sin(t * 2) * 0.2;
  });

  const ringRadius = 0.8 + severity * 0.6;

  return (
    <group>
      {/* Warning ring */}
      <mesh ref={ringRef} position={position}>
        <torusGeometry args={[ringRadius, 0.06, 8, 32]} />
        <meshBasicMaterial
          color="#ef4444"
          transparent
          opacity={0.6}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Severity indicator billboard */}
      <Billboard position={[position.x, position.y + ringRadius + 0.4, position.z]}>
        <Text
          fontSize={0.18}
          color="#fca5a5"
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.01}
          outlineColor="#000"
        >
          {`⚠ SPOF: ${label}`}
        </Text>
      </Billboard>
    </group>
  );
}

/* ─── HubMarker ──────────────────────────────────────────────────────────── */

interface HubMarkerProps {
  position: THREE.Vector3;
  label:    string;
}

/**
 * Amber halo for over-connected hub nodes.
 */
function HubMarker({ position, label }: HubMarkerProps): React.JSX.Element {
  const haloRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    if (!haloRef.current) return;
    const t = clock.getElapsedTime();
    (haloRef.current.material as THREE.MeshBasicMaterial).opacity =
      0.08 + Math.sin(t * 1.2) * 0.04;
  });

  return (
    <group>
      <mesh ref={haloRef} position={position}>
        <sphereGeometry args={[1.4, 12, 12]} />
        <meshBasicMaterial
          color="#f59e0b"
          transparent
          opacity={0.1}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>
    </group>
  );
}

/* ─── CriticalPathGlow ───────────────────────────────────────────────────── */

interface CriticalPathGlowProps {
  positions: THREE.Vector3[];
}

/**
 * Bright white/cyan tube tracing the critical path through the graph.
 */
function CriticalPathGlow({ positions }: CriticalPathGlowProps): React.JSX.Element | null {
  const tubeMat = useRef<THREE.MeshBasicMaterial>(null!);

  const curve = useMemo(
    () => new THREE.CatmullRomCurve3(positions),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [positions.length]
  );

  const tubeGeo = useMemo(
    () => new THREE.TubeGeometry(curve, positions.length * 5, 0.06, 8, false),
    [curve, positions.length]
  );

  useFrame(({ clock }) => {
    if (!tubeMat.current) return;
    const t = clock.getElapsedTime();
    tubeMat.current.opacity = 0.6 + Math.sin(t * 2) * 0.2;
  });

  if (positions.length < 2) return null;

  return (
    <mesh geometry={tubeGeo}>
      <meshBasicMaterial
        ref={tubeMat}
        color="#e0f2fe"
        transparent
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}

/* ─── ClusterDisc ────────────────────────────────────────────────────────── */

interface ClusterDiscProps {
  centroid: THREE.Vector3;
  radius:   number;
  color:    string;
  index:    number;
}

/**
 * Translucent ground-plane disc colour-coding a cluster region.
 */
function ClusterDisc({ centroid, radius, color, index }: ClusterDiscProps): React.JSX.Element {
  const discRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    if (!discRef.current) return;
    const t = clock.getElapsedTime();
    (discRef.current.material as THREE.MeshBasicMaterial).opacity =
      0.04 + Math.sin(t * 0.5 + index) * 0.01;
  });

  return (
    <mesh
      ref={discRef}
      position={[centroid.x, centroid.y - 0.5, centroid.z]}
      rotation={[Math.PI / 2, 0, 0]}
    >
      <circleGeometry args={[radius + 1, 32]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.05}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* ─── Main AnalyticsOverlay ──────────────────────────────────────────────── */

interface AnalyticsOverlayProps {
  analytics: AnalyticsResult;
  nodeMap:   Map<string, THREE.Vector3>;
}

/**
 * AnalyticsOverlay — composes all analysis visual layers in the R3F scene.
 *
 * @param analytics - AnalyticsResult from useAnalytics hook.
 * @param nodeMap   - Map from node ID → world Vector3 (from useNodePositions).
 */
export function AnalyticsOverlay({
  analytics,
  nodeMap,
}: AnalyticsOverlayProps): React.JSX.Element {
  /** Map bottleneck nodeIds → positions. */
  const bottleneckPositions = analytics.bottlenecks
    .map((b) => ({ pos: nodeMap.get(b.node_id), ...b }))
    .filter((b): b is typeof b & { pos: THREE.Vector3 } => !!b.pos);

  /** Map hub nodeIds → positions. */
  const hubPositions = analytics.hubs
    .map((h) => ({ pos: nodeMap.get(h.node_id), ...h }))
    .filter((h): h is typeof h & { pos: THREE.Vector3 } => !!h.pos);

  /** Critical path positions. */
  const criticalPathPositions = (analytics.critical_path?.node_ids ?? [])
    .map((id) => nodeMap.get(id))
    .filter((pos): pos is THREE.Vector3 => !!pos);

  /**
   * Per-cluster: compute centroid and bounding radius.
   * We colour each cluster with a distinct hue.
   */
  const clusterData = analytics.clusters.slice(0, 8).map((cluster, i) => {
    const positions = cluster.node_ids
      .map((id) => nodeMap.get(id))
      .filter((p): p is THREE.Vector3 => !!p);

    if (positions.length === 0) return null;

    const centroid = new THREE.Vector3();
    positions.forEach((p) => centroid.add(p));
    centroid.divideScalar(positions.length);

    const radius = Math.max(
      ...positions.map((p) => p.distanceTo(centroid)),
      1.5
    );

    return { centroid, radius, color: CLUSTER_COLORS[i % CLUSTER_COLORS.length]!, index: i };
  }).filter(Boolean) as { centroid: THREE.Vector3; radius: number; color: string; index: number }[];

  return (
    <group>
      {/* Cluster ground discs */}
      {clusterData.map((cd, i) => (
        <ClusterDisc key={i} {...cd} />
      ))}

      {/* Critical path glow tube */}
      {criticalPathPositions.length >= 2 && (
        <CriticalPathGlow positions={criticalPathPositions} />
      )}

      {/* Hub halos */}
      {hubPositions.map((h) => (
        <HubMarker key={h.node_id} position={h.pos} label={h.label} />
      ))}

      {/* Bottleneck warning rings */}
      {bottleneckPositions.map((b) => (
        <BottleneckMarker
          key={b.node_id}
          position={b.pos}
          severity={b.severity}
          label={b.label}
        />
      ))}
    </group>
  );
}
