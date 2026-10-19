import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

test("Maximize fills the screen and Restore brings the card back", async () => {
  const user = userEvent.setup();
  render(
    <Sheet title="Add a reference" onClose={vi.fn()}>
      <p>body</p>
    </Sheet>,
  );
  const dialog = screen.getByRole("dialog", { name: "Add a reference" });
  expect(dialog).not.toHaveClass("inset-0");

  await user.click(screen.getByRole("button", { name: "Maximize" }));
  expect(dialog).toHaveClass("fixed", "inset-0");
  expect(dialog).not.toHaveClass("max-w-md");

  await user.click(screen.getByRole("button", { name: "Restore" }));
  expect(dialog).not.toHaveClass("inset-0");
  expect(dialog).toHaveClass("max-w-md");
});

test("A sheet opened inside another sheet stacks above it", () => {
  render(
    <Sheet title="Add a door zone" onClose={vi.fn()}>
      <Sheet title="Snapshot from a recent clip" onClose={vi.fn()}>
        <p>picker</p>
      </Sheet>
    </Sheet>,
  );
  const layer = (name: string) => Number(getComputedStyle(screen.getByRole("dialog", { name }).parentElement!).zIndex);
  expect(layer("Snapshot from a recent clip")).toBeGreaterThan(layer("Add a door zone"));
});
