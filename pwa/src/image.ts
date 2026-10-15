/** Reference photos are shrunk in the browser before upload. */
export const MAX_SIDE = 768;
export const MAX_BYTES = 200_000;

/** The size that fits within `max` on its longer side, keeping the aspect ratio; never enlarges. */
export function fitWithin(width: number, height: number, max: number) {
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** Turns a picked photo into a base64 JPEG of at most MAX_SIDE px and MAX_BYTES. */
export type Resize = (file: Blob) => Promise<string>;

export const toJpeg: Resize = async (file) => {
  const bitmap = await createImageBitmap(file);
  const { width, height } = fitWithin(bitmap.width, bitmap.height, MAX_SIDE);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  let blob = await encode(canvas, 0.8);
  if (blob.size > MAX_BYTES) blob = await encode(canvas, 0.6);
  return base64(blob);
};

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
