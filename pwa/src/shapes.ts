import type { Box } from "./api/types";

/** A point in fractions of an image: (0, 0) top left, (1, 1) bottom right. */
export interface Point {
  x: number;
  y: number;
}

export type ShapeKind = "box" | "line";

/** A drawn box (corners) or line (ends), in fractions of the image. */
export interface Shape {
  kind: ShapeKind;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/** Drags shorter than this (in fractions of the image) draw nothing. */
export const MIN_SIZE = 0.02;

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

export function clampPoint(p: Point): Point {
  return { x: clamp01(p.x), y: clamp01(p.y) };
}

/** The shape a drag from `a` to `b` draws, or null when it is too small. */
export function dragToShape(kind: ShapeKind, a: Point, b: Point): Shape | null {
  const [p, q] = [clampPoint(a), clampPoint(b)];
  if (kind === "box") {
    if (Math.abs(q.x - p.x) < MIN_SIZE || Math.abs(q.y - p.y) < MIN_SIZE) return null;
    return { kind, x1: Math.min(p.x, q.x), y1: Math.min(p.y, q.y), x2: Math.max(p.x, q.x), y2: Math.max(p.y, q.y) };
  }
  if (Math.hypot(q.x - p.x, q.y - p.y) < MIN_SIZE) return null;
  return { kind, x1: p.x, y1: p.y, x2: q.x, y2: q.y };
}

const round3 = (v: number) => Math.round(v * 1000) / 1000;

/** A box shape as x, y, width, height rounded to 3 places, never past the image edge. */
export function shapeToBox(shape: Shape): Box {
  const x = round3(Math.min(shape.x1, shape.x2));
  const y = round3(Math.min(shape.y1, shape.y2));
  const width = Math.min(round3(Math.abs(shape.x2 - shape.x1)), round3(1 - x));
  const height = Math.min(round3(Math.abs(shape.y2 - shape.y1)), round3(1 - y));
  return { x, y, width, height };
}

/** The box shape for a box in fractions of an image. */
export function boxShape(b: Box): Shape {
  return { kind: "box", x1: b.x, y1: b.y, x2: b.x + b.width, y2: b.y + b.height };
}
