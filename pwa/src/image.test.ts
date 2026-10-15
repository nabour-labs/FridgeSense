import { fitWithin } from "./image";

test("a landscape photo shrinks so its longer side is 768", () => {
  expect(fitWithin(4032, 3024, 768)).toEqual({ width: 768, height: 576 });
});

test("a portrait photo shrinks by its height", () => {
  expect(fitWithin(3024, 4032, 768)).toEqual({ width: 576, height: 768 });
});

test("a small photo is never enlarged", () => {
  expect(fitWithin(640, 480, 768)).toEqual({ width: 640, height: 480 });
});
