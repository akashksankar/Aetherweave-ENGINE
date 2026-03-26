/**
 * @fileoverview useNodePositions — derives stable 3D positions from an ArchGraph.
 *
 * Converts the 2D positions stored in the ArchGraph nodes (populated by
 * the NetworkX spring layout on the backend) into 3D world-space coordinates
 * for the R3F scene.
 *
 * Layout algorithm:
 *   - x, y from the backend's NetworkX spring layout (range ~[-1, 1])
 *   - z is derived from the node's fitness value so high-fitness nodes
 *     "float" higher in the Z axis, creating a 3D fitness landscape.
 *   - All coordinates are scaled by SCALE_FACTOR to give comfortable
 *     camera distances.
 *
 * Positions are memoised on node IDs so the mesh only re-animates when
 * the graph actually changes (not on every evolution generation).
 *
 * @module hooks/use-node-positions
 */

"use client";

import { useMemo } from "react";
import * as THREE from "three";
import type { ArchGraph, ArchNode } from "@aetherweave/shared";

/** World-space scale factor applied to all coordinates. */
const SCALE = 8;

/** How far nodes spread on the Z axis based on fitness. */
const Z_SCALE = 4;

export interface NodePosition {
  id:       string;
  position: THREE.Vector3;
  color:    string;
  type:     string;
  label:    string;
  fitness:  number;
  size:     number;
}

export interface EdgePosition {
  id:     string;
  source: THREE.Vector3;
  target: THREE.Vector3;
  weight: number;
  label:  string;
}

/**
 * Node type → bioluminescent hex colour mapping.
 * Each type has a distinct colour to make the neural forest visually scannable.
 */
const NODE_COLORS: Record<string, string> = {
  service:  "#7c3aed",  // violet — core services
  database: "#0ea5e9",  // cyan   — data stores
  gateway:  "#f59e0b",  // amber  — API gateways
  cache:    "#10b981",  // emerald — caches
  queue:    "#ec4899",  // pink   — message queues
  ml:       "#a78bfa",  // lavender — ML inference
  cdn:      "#38bdf8",  // sky   — CDN nodes
  auth:     "#fb923c",  // orange — auth services
  monitor:  "#84cc16",  // lime  — monitoring
  edge:     "#e879f9",  // fuchsia — edge nodes
};

const DEFAULT_COLOR = "#6366f1";

/**
 * Returns position, colour, and size arrays for all nodes and edges
 * in the given ArchGraph. Memoised on graph.id to avoid recalculation.
 *
 * @param graph - The active ArchGraph from the Zustand store (may be null).
 * @returns { nodes: NodePosition[], edges: EdgePosition[], nodeMap }
 */
export function useNodePositions(graph: ArchGraph | null): {
  nodes:   NodePosition[];
  edges:   EdgePosition[];
  nodeMap: Map<string, THREE.Vector3>;
} {
  return useMemo(() => {
    if (!graph || !graph.nodes?.length) {
      return { nodes: [], edges: [], nodeMap: new Map() };
    }

    const nodeMap = new Map<string, THREE.Vector3>();

    /** Convert ArchNode → NodePosition with 3D world coordinates. */
    const nodes: NodePosition[] = graph.nodes.map((n: ArchNode) => {
      const rawX = (n.position?.x ?? 0);
      const rawY = (n.position?.y ?? 0);
      const zFromFitness = (n.fitness ?? 0.5) * Z_SCALE - Z_SCALE / 2;

      const pos = new THREE.Vector3(
        rawX * SCALE,
        rawY * SCALE,
        zFromFitness,
      );
      nodeMap.set(n.id, pos);

      return {
        id:       n.id,
        position: pos,
        color:    NODE_COLORS[n.type] ?? DEFAULT_COLOR,
        type:     n.type,
        label:    n.label,
        fitness:  n.fitness ?? 0.5,
        size:     0.3 + (n.fitness ?? 0.5) * 0.4, // 0.3 → 0.7
      };
    });

    /** Convert ArchEdge → EdgePosition using the nodeMap. */
    const edges: EdgePosition[] = (graph.edges ?? [])
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        id:     e.id,
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!,
        weight: e.weight ?? 0.5,
        label:  e.label ?? "HTTP",
      }));

    return { nodes, edges, nodeMap };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph?.id, graph?.nodes?.length]);
}
