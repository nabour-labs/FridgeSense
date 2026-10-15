import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import { Select } from "./Select";

const OPTIONS = [
  { value: "dairy", label: "Dairy" },
  { value: "produce", label: "Produce" },
  { value: "other", label: "Other" },
];

function Harness() {
  const [value, setValue] = useState("other");
  return (
    <>
      <label htmlFor="cat">Category</label>
      <Select id="cat" value={value} onChange={setValue} options={OPTIONS} />
      <output>{value}</output>
    </>
  );
}

test("renders as a combobox showing the current option, not a native select", () => {
  render(<Harness />);
  const box = screen.getByRole("combobox", { name: "Category" });
  expect(box.tagName).not.toBe("SELECT");
  expect(box).toHaveTextContent("Other");
  expect(box).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

test("clicking an option selects it and closes the list", async () => {
  render(<Harness />);
  await userEvent.click(screen.getByRole("combobox", { name: "Category" }));
  expect(screen.getByRole("option", { name: "Other" })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("option", { name: "Dairy" }));
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(screen.getByRole("combobox")).toHaveTextContent("Dairy");
  expect(screen.getByRole("status")).toHaveTextContent("dairy");
});

test("arrow keys and Enter pick an option from the keyboard", async () => {
  render(<Harness />);
  screen.getByRole("combobox").focus();
  await userEvent.keyboard("{ArrowDown}");
  expect(screen.getByRole("listbox")).toBeInTheDocument();
  await userEvent.keyboard("{Home}{ArrowDown}{Enter}");
  expect(screen.getByRole("status")).toHaveTextContent("produce");
  expect(screen.getByRole("combobox")).toHaveFocus();
});

test("Escape closes the list without closing the surrounding sheet", async () => {
  const onKey = vi.fn();
  addEventListener("keydown", onKey);
  render(<Harness />);
  await userEvent.click(screen.getByRole("combobox"));
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(onKey).not.toHaveBeenCalledWith(expect.objectContaining({ key: "Escape" }));
  expect(screen.getByRole("status")).toHaveTextContent("other");
  removeEventListener("keydown", onKey);
});
