import type { Shape } from "./shapes";

const MARKUP_RED = "#ef4444";
/** Reference photos are shrunk in the browser before upload. */
export const MAX_SIDE = 768;
export const MAX_BYTES = 200_000;

/** The size that fits within `max` on its longer side, keeping the aspect ratio; never enlarges. */
export function fitWithin(width: number, height: number, max: number) {
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/**
 * Turns a picked photo or snapshot into a base64 JPEG of at most MAX_SIDE px and MAX_BYTES,
 * with any `shapes` (fractions of the image) drawn on it in red.
 */
export type Resize = (file: Blob, shapes?: Shape[]) => Promise<string>;

export const toJpeg: Resize = async (file, shapes = []) => {
  const bitmap = await createImageBitmap(file);
  const { width, height } = fitWithin(bitmap.width, bitmap.height, MAX_SIDE);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  drawShapes(ctx, shapes, width, height);
  let blob = await encode(canvas, 0.8);
  if (blob.size > MAX_BYTES) blob = await encode(canvas, 0.6);
  return base64(blob);
};

/** Strokes the shapes in red, about 3 px wide on a 768 px image. */
export function drawShapes(ctx: CanvasRenderingContext2D, shapes: Shape[], width: number, height: number) {
  if (!shapes.length) return;
  ctx.strokeStyle = MARKUP_RED;
  ctx.lineWidth = Math.max(2, Math.round(Math.max(width, height) / 256));
  ctx.lineCap = "round";
  for (const s of shapes) {
    const [x1, y1, x2, y2] = [s.x1 * width, s.y1 * height, s.x2 * width, s.y2 * height];
    ctx.beginPath();
    if (s.kind === "box") ctx.rect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
    else {
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
    }
    ctx.stroke();
  }
}

function encode(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("JPEG encoding failed"))), "image/jpeg", quality),
  );
}

async function base64(blob: Blob): Promise<string> {
  const url = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
  return url.slice(url.indexOf(",") + 1);
}
