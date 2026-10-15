import { itemIcon } from "./itemIcon";

// Item icons from name
test("icons come from the item name", () => {
  expect(itemIcon("milk", "dairy")).toBe("🥛");
  expect(itemIcon("Apple", "produce")).toBe("🍎");
  expect(itemIcon("leftover pasta", "leftovers")).toBe("🍝");
  expect(itemIcon("Greek yogurt", "dairy")).toBe("🥣");
  expect(itemIcon("Orange juice", "beverage")).toBe("🧃");
});

// Item icon falls back to category, then a plate
test("unknown names fall back to the category, then a plate", () => {
  expect(itemIcon("kefir", "dairy")).toBe("🧀");
  expect(itemIcon("mystery jar", "other")).toBe("🍽️");
});
