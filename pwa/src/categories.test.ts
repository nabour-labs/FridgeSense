import { CATEGORIES } from "./categories";

// Must match backend analysis.CATEGORIES: the API answers 400 "unknown category" otherwise.
test("categories match the backend list", () => {
  expect(CATEGORIES).toEqual([
    "dairy",
    "produce",
    "meat",
    "seafood",
    "beverage",
    "snack",
    "condiment",
    "leftovers",
    "bakery",
    "frozen",
    "other",
  ]);
});
