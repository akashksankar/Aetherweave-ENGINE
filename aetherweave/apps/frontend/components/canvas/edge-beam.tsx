/**
 * @fileoverview EdgeBeam — Animated light-beam tube connecting two nodes
 *
 * Each edge in the architecture graph is rendered as a thin tube (TubeGeometry)
 * that carries an animated "data packet" — a small sphere that travels
 * along the tube from source to target, representing data flow.
 *
 * Rendering:
 *   - TubeGeometry with a CatmullRomCurve3 (slight mid-point curve for
 *     organic feel rather than straight lines).
 *   - Edge colour blends between source and target node colours.
 *   - Tube opacity is proportional to edge weight (heavier = brighter).
 *   - Additive blending so overlapping beams glow correctly.
 *   - A data-packet sphere travels along the path, looping continuously.
 *   - Tube brightens during evolution runs (evolutionActive prop).
 *
 * @module components/canvas/edge-beam
 */

"use client";

import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { EdgePosition } from "@/hooks/use-node-positions";

interface EdgeBeamProps {
  edge: EdgePosition;
  sourceColor: string;
  targetColor: string;
  evolutionActive: boolean;
}

/** How many tube segments per edge (quality vs. perf trade-off). */
const TUBE_SEGMENTS = 20;
const TUBE_RADIUS = 0.02;

/**
 * EdgeBeam component — animated tube + travelling data-packet sphere.
 *
 * @param edge           - EdgePosition with source/target Vector3s.
 * @param sourceColor    - Hex colour of the source node.
 * @param targetColor    - Hex colour of the target node.
 * @param evolutionActive - Whether evolution is currently running.
 */
export function EdgeBeam({
  edge,
  sourceColor,
  targetColor,
  evolutionActive,
}: EdgeBeamProps): React.JSX.Element {
  const packetRef = useRef<THREE.Mesh>(null!);
  const tubeMat   = useRef<THREE.MeshBasicMaterial>(null!);

  /** Progress of the data packet along the curve [0, 1]. Incremented each frame. */
  const progressRef = useRef(Math.random()); // stagger starting positions

  /** Mid-point raised/lowered slightly for an organic arc. */
  const mid = useMemo(() => {
    const m = new THREE.Vector3().lerpVectors(edge.source, edge.target, 0.5);
    // Add a slight perpendicular offset for visual clarity on overlapping edges
    m.x += (Math.random() - 0.5) * 0.8;
    m.y += Math.abs(edge.source.y - edge.target.y) * 0.2 + 0.5;
    return m;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edge.id]);

  /** CatmullRom curve through source → mid → target. */
  const curve = useMemo(
    () => new THREE.CatmullRomCurve3([edge.source, mid, edge.target]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [edge.id]
  );

  /** Tube geometry built from the curve. */
  const tubeGeo = useMemo(
    () => new THREE.TubeGeometry(curve, TUBE_SEGMENTS, TUBE_RADIUS, 6, false),
    [curve]
  );

  /** Blended edge colour between source and target. */
  const edgeColor = useMemo(() => {
    const s = new THREE.Color(sourceColor);
    const t = new THREE.Color(targetColor);
    return s.lerp(t, 0.5);
  }, [sourceColor, targetColor]);

  /** Advance the data packet along the curve each frame. */
  useFrame((_, delta) => {
    progressRef.current = (progressRef.current + delta * 0.35) % 1;

    if (packetRef.current) {
      const pt = curve.getPoint(progressRef.current);
      packetRef.current.position.set(pt.x, pt.y, pt.z);
    }

    if (tubeMat.current) {
      const targetOpacity = evolutionActive
        ? 0.55 + edge.weight * 0.3
        : 0.18 + edge.weight * 0.2;
      tubeMat.current.opacity = THREE.MathUtils.lerp(
        tubeMat.current.opacity,
        targetOpacity,
        0.05
      );
    }
  });

  return (
    <group>
      {/* ── Edge tube ───────────────────────────────────────────────────── */}
      <mesh geometry={tubeGeo}>
        <meshBasicMaterial
          ref={tubeMat}
          color={edgeColor}
          transparent
          opacity={0.18 + edge.weight * 0.2}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ── Data packet sphere ────────────────────────────────────────────── */}
      <mesh ref={packetRef} position={edge.source}>
        <sphereGeometry args={[0.06, 6, 6]} />
        <meshBasicMaterial
          color={edgeColor}
          transparent
          opacity={evolutionActive ? 1.0 : 0.6}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}
