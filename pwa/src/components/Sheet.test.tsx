import { render, screen } from "@testing-library/react";
import { Sheet } from "./Sheet";

test("Other dialogs keep their width", () => {
  render(
    <Sheet title="Add item" onClose={vi.fn()}>
      <p>body</p>
    </Sheet>,
  );
  const dialog = screen.getByRole("dialog", { name: "Add item" });
  expect(dialog).toHaveClass("max-w-md");
  expect(dialog).not.toHaveClass("sm:max-w-3xl");
});
