import { readFileSync } from "node:fs";

const css = readFileSync("src/index.css", "utf8");

// Theme tokens
test("the theme defines brand and warm colours and the bundled font", () => {
  const theme = css.match(/@theme\s*\{[\s\S]*?\n\}/)?.[0] ?? "";
  expect(theme).toContain("--color-brand-500");
  expect(theme).toContain("--color-warm-500");
  expect(css).toMatch(/@import\s+["']@fontsource-variable\/plus-jakarta-sans["']/);
});

// Reduced motion
test("animations and transitions are off under reduced motion", () => {
  const block = css.match(/@media \(prefers-reduced-motion: reduce\)\s*\{[\s\S]*?\n\}/)?.[0] ?? "";
  expect(block).toMatch(/animation-duration:\s*0\.01ms/);
  expect(block).toMatch(/transition-duration:\s*0\.01ms/);
});
