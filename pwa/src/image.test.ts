import { cropRect, fitWithin } from "./image";

test("a landscape photo shrinks so its longer side is 768", () => {
  expect(fitWithin(4032, 3024, 768)).toEqual({ width: 768, height: 576 });
});

test("a portrait photo shrinks by its height", () => {
  expect(fitWithin(3024, 4032, 768)).toEqual({ width: 576, height: 768 });
});

test("a small photo is never enlarged", () => {
  expect(fitWithin(640, 480, 768)).toEqual({ width: 640, height: 480 });
});

// Crop to the box: a box from 10%, 10% to 40%, 50% on a 1000×800 image
test("a crop box becomes whole pixels of the image", () => {
  expect(cropRect(1000, 800, { kind: "box", x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.5 })).toEqual({ x: 100, y: 80, width: 300, height: 320 });
});

test("a crop is at least 1 px and stays inside the image", () => {
  const r = cropRect(3, 3, { kind: "box", x1: 0.5, y1: 0.5, x2: 0.51, y2: 0.51 });
  expect(r.width).toBeGreaterThanOrEqual(1);
  expect(r.height).toBeGreaterThanOrEqual(1);
  expect(r.x + r.width).toBeLessThanOrEqual(3);
  expect(r.y + r.height).toBeLessThanOrEqual(3);
  expect(cropRect(1000, 1000, { kind: "box", x1: 1, y1: 1, x2: 0.9, y2: 0.9 })).toEqual({ x: 900, y: 900, width: 100, height: 100 });
});
