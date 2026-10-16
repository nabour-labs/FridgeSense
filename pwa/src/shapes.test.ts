import { clampPoint, dragToShape, shapeToBox } from "./shapes";

// Draw a zone / Draw on the image: a box from (0.1, 0.1) to (0.4, 0.5)
test("a drag makes a box between its corners, in any direction", () => {
  expect(dragToShape("box", { x: 0.4, y: 0.5 }, { x: 0.1, y: 0.1 })).toEqual({ kind: "box", x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.5 });
});

test("a drag makes a line from start to end", () => {
  expect(dragToShape("line", { x: 0.5, y: 0.5 }, { x: 0.9, y: 0.9 })).toEqual({ kind: "line", x1: 0.5, y1: 0.5, x2: 0.9, y2: 0.9 });
});

// Tiny drag ignored
test.each([
  [{ x: 0.5, y: 0.5 }, { x: 0.51, y: 0.9 }],
  [{ x: 0.5, y: 0.5 }, { x: 0.9, y: 0.515 }],
])("a box under 2%% wide or tall is ignored", (a, b) => {
  expect(dragToShape("box", a, b)).toBeNull();
});

test("a line under 2% long is ignored", () => {
  expect(dragToShape("line", { x: 0.5, y: 0.5 }, { x: 0.51, y: 0.51 })).toBeNull();
  expect(dragToShape("line", { x: 0.5, y: 0.5 }, { x: 0.5, y: 0.53 })).not.toBeNull();
});

test("points are kept inside the image", () => {
  expect(clampPoint({ x: -0.2, y: 1.4 })).toEqual({ x: 0, y: 1 });
  expect(clampPoint({ x: 0.3, y: 0.7 })).toEqual({ x: 0.3, y: 0.7 });
});

// Add a door reference: drag from 38%, 32% to 59%, 62% gives this box
test("a box shape becomes x, y, width, height rounded to 3 places", () => {
  const shape = dragToShape("box", { x: 0.38, y: 0.32 }, { x: 0.59, y: 0.62 })!;
  expect(shapeToBox(shape)).toEqual({ x: 0.38, y: 0.32, width: 0.21, height: 0.3 });
});

test("rounding never pushes a box past the image edge", () => {
  const shape = dragToShape("box", { x: 0.6666, y: 0.3333 }, { x: 1, y: 1 })!;
  const box = shapeToBox(shape);
  expect(box.x + box.width).toBeLessThanOrEqual(1);
  expect(box.y + box.height).toBeLessThanOrEqual(1);
});
