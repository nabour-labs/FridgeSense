import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { Config as ConfigData, Reference } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { fakeApi } from "../test-utils";
import { Config } from "./Config";

function ref(id: string, annotation: string): Reference {
  return { id, annotation, image: "/9j/AAAA", created_at: "2026-10-15T08:00:00.000Z" };
}

const MILK = ref("r1", "milk bag");

function renderConfig(
  config: ConfigData,
  { role = "owner", api: overrides = {}, resize = vi.fn().mockResolvedValue("/9j/RESIZED") } = {} as {
    role?: "owner" | "viewer";
    api?: Partial<Record<keyof Api, unknown>>;
    resize?: (file: Blob) => Promise<string>;
  },
) {
  const api = fakeApi({ config: vi.fn().mockResolvedValue(config), ...overrides });
  const report = vi.fn();
  render(
    <AppContext.Provider value={{ api, role, report, online: vi.fn(), go: vi.fn() }}>
      <Config resize={resize} />
    </AppContext.Provider>,
  );
  return { api, report, resize };
}

// Viewer sees read-only config
test("a viewer sees references and instructions without controls", async () => {
  renderConfig({ instructions: "Count yogurt cups individually.", references: [MILK] }, { role: "viewer" });
  const refs = await screen.findByRole("region", { name: "Reference images" });
  expect(within(refs).getByText("milk bag")).toBeInTheDocument();
  expect(within(refs).getByRole("img", { name: "milk bag" })).toHaveAttribute("src", "data:image/jpeg;base64,/9j/AAAA");
  expect(screen.getByText("Count yogurt cups individually.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Add|Delete|Save/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});

const PHOTO = new File([new Uint8Array([1, 2, 3])], "IMG_0001.jpg", { type: "image/jpeg" });

async function openAdd(annotation?: string) {
  await userEvent.click(await screen.findByRole("button", { name: "Add" }));
  await userEvent.upload(screen.getByLabelText("Photo"), PHOTO);
  if (annotation) await userEvent.type(screen.getByLabelText("Annotation"), annotation);
}

// Add a reference
test("adding a reference resizes the photo, uploads it and lists it", async () => {
  const added = { instructions: "", references: [ref("r2", "soda can")] };
  const { api, resize } = renderConfig(
    { instructions: "", references: [] },
    { api: { addReference: vi.fn().mockResolvedValue(added) } },
  );
  await openAdd("soda can");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  expect(resize).toHaveBeenCalledWith(PHOTO);
  expect(api.addReference).toHaveBeenCalledWith("soda can", "/9j/RESIZED");
  const refs = screen.getByRole("region", { name: "Reference images" });
  expect(await within(refs).findByText("soda can")).toBeInTheDocument();
  expect(screen.queryByLabelText("Photo")).not.toBeInTheDocument();
});

// Annotation required
test("Save stays disabled until there is an annotation", async () => {
  const { api } = renderConfig({ instructions: "", references: [] });
  await openAdd();
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Annotation"), "   ");
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" })).toBeDisabled();
  expect(api.addReference).not.toHaveBeenCalled();
});

// Limit reached
test("with 6 references the count reads 6 of 6 and Add is disabled", async () => {
  const six = Array.from({ length: 6 }, (_, n) => ref(`r${n}`, `item ${n}`));
  renderConfig({ instructions: "", references: six });
  expect(await screen.findByText("6 of 6")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
});

test("the count shows how many of 6 are used", async () => {
  renderConfig({ instructions: "", references: [MILK] });
  expect(await screen.findByText("1 of 6")).toBeInTheDocument();
});

// Delete a reference
test("deleting a reference asks first, then removes it", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  const { api } = renderConfig(
    { instructions: "", references: [MILK] },
    { api: { deleteReference: vi.fn().mockResolvedValue({ instructions: "", references: [] }) } },
  );
  const del = await screen.findByRole("button", { name: "Delete milk bag" });
  await userEvent.click(del);
  expect(api.deleteReference).not.toHaveBeenCalled();
  await userEvent.click(del);
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(api.deleteReference).toHaveBeenCalledWith("r1");
  expect(await screen.findByText("0 of 6")).toBeInTheDocument();
  expect(screen.queryByText("milk bag")).not.toBeInTheDocument();
  confirm.mockRestore();
});

// Upload refused
test.each([
  [400, "image must be a JPEG of at most 200 KB"],
  [409, "at most 6 reference images"],
])("a %i from the API shows its message and keeps the list", async (status, message) => {
  renderConfig(
    { instructions: "", references: [MILK] },
    { api: { addReference: vi.fn().mockRejectedValue(new ApiError(status, message)) } },
  );
  await openAdd("soda can");
  await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(message);
  const refs = screen.getByRole("region", { name: "Reference images" });
  expect(within(refs).getByText("milk bag")).toBeInTheDocument();
  expect(within(refs).queryByText("soda can")).not.toBeInTheDocument();
});

function instructionsBox() {
  return screen.findByRole("textbox", { name: "Custom instructions" });
}

function saveInstructionsButton() {
  const section = screen.getByRole("region", { name: "Custom instructions" });
  return within(section).getByRole("button", { name: "Save" });
}

// Save instructions
test("saving instructions sends them and confirms with Saved", async () => {
  const saved = { instructions: "Count yogurt cups individually.", references: [] };
  const { api } = renderConfig(
    { instructions: "", references: [] },
    { api: { saveInstructions: vi.fn().mockResolvedValue(saved) } },
  );
  await userEvent.type(await instructionsBox(), "Count yogurt cups individually.");
  expect(screen.getByText("31 / 1000")).toBeInTheDocument();
  await userEvent.click(saveInstructionsButton());
  expect(api.saveInstructions).toHaveBeenCalledWith("Count yogurt cups individually.");
  expect(await screen.findByText("Saved")).toBeInTheDocument();
  expect(saveInstructionsButton()).toBeDisabled();
});

// Over the limit
test("over 1000 characters the count shows it and Save is disabled", async () => {
  const { api } = renderConfig({ instructions: "x".repeat(1000), references: [] });
  const box = await instructionsBox();
  await userEvent.type(box, "y");
  expect(screen.getByText("1001 / 1000")).toBeInTheDocument();
  expect(saveInstructionsButton()).toBeDisabled();
  expect(api.saveInstructions).not.toHaveBeenCalled();
});

// Unchanged text
test("Save is disabled while the text equals the saved instructions", async () => {
  renderConfig({ instructions: "Count yogurt cups individually.", references: [] });
  expect(await instructionsBox()).toHaveValue("Count yogurt cups individually.");
  expect(saveInstructionsButton()).toBeDisabled();
});
