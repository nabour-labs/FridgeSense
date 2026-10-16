import { useRef, useState, type PointerEvent } from "react";
import { clampPoint, dragToShape, type Point, type Shape, type ShapeKind } from "../shapes";

export const MARKUP_RED = "#ef4444";

/** One shape drawn over the image, in an SVG whose units are percent of the image. */
export function ShapeMark({ shape, color = MARKUP_RED, draft = false }: { shape: Shape; color?: string; draft?: boolean }) {
  const common = {
    stroke: color,
    strokeWidth: 3,
    vectorEffect: "non-scaling-stroke" as const,
    strokeDasharray: draft ? "6 4" : undefined,
    "data-testid": draft ? "markup-draft" : "markup-shape",
  };
  if (shape.kind === "line") {
    return <line x1={shape.x1 * 100} y1={shape.y1 * 100} x2={shape.x2 * 100} y2={shape.y2 * 100} strokeLinecap="round" {...common} />;
  }
  return (
    <rect
      x={Math.min(shape.x1, shape.x2) * 100}
      y={Math.min(shape.y1, shape.y2) * 100}
      width={Math.abs(shape.x2 - shape.x1) * 100}
      height={Math.abs(shape.y2 - shape.y1) * 100}
      fill={`${color}22`}
      {...common}
    />
  );
}

/** An image with shapes over it. Unless read-only, dragging draws a `tool` shape. */
export function ImageMarkup({
  src,
  alt,
  shapes,
  onChange,
  tool = "box",
  single = false,
  readOnly = false,
  color = MARKUP_RED,
  className = "",
}: {
  src: string;
  alt: string;
  shapes: Shape[];
  onChange?: (shapes: Shape[]) => void;
  tool?: ShapeKind;
  /** A new shape replaces the old one (one box per image). */
  single?: boolean;
  readOnly?: boolean;
  color?: string;
  className?: string;
}) {
  const start = useRef<Point | null>(null);
  const [draft, setDraft] = useState<Shape | null>(null);

  function point(e: PointerEvent<HTMLDivElement>): Point {
    const r = e.currentTarget.getBoundingClientRect();
    return clampPoint({ x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
  }

  function down(e: PointerEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    start.current = point(e);
  }

  function move(e: PointerEvent<HTMLDivElement>) {
    if (!start.current) return;
    const p = point(e);
    setDraft({ kind: tool, x1: start.current.x, y1: start.current.y, x2: p.x, y2: p.y });
  }

  function up(e: PointerEvent<HTMLDivElement>) {
    if (!start.current) return;
    const shape = dragToShape(tool, start.current, point(e));
    start.current = null;
    setDraft(null);
    if (shape) onChange?.(single ? [shape] : [...shapes, shape]);
  }

  return (
    <div
      data-testid="markup-surface"
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={() => {
        start.current = null;
        setDraft(null);
      }}
      className={`relative select-none overflow-hidden rounded-xl ${readOnly ? "" : "cursor-crosshair touch-none"} ${className}`}
    >
      <img src={src} alt={alt} draggable={false} className="block w-full" />
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden className="pointer-events-none absolute inset-0 size-full">
        {shapes.map((s, n) => (
          <ShapeMark key={n} shape={s} color={color} />
        ))}
        {draft && <ShapeMark shape={draft} color={color} draft />}
      </svg>
    </div>
  );
}
