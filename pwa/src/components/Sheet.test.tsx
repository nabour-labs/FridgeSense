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
