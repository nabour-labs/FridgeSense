import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { fakeApi, signedIn } from "./test-utils";

// User sign-in
test("signing in as a user shows the full app without the demo badge", async () => {
  location.hash = "";
  const api = fakeApi({
    signIn: vi.fn().mockResolvedValue({ token: "ut", expires_at: new Date(Date.now() + 3600_000).toISOString(), role: "user" }),
  });
  render(<App api={api} />);
  await userEvent.type(screen.getByLabelText("Passcode"), "come-in");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Fridge" })).toBeInTheDocument();
  expect(localStorage.getItem("fridgesense.role")).toBe("user");
  expect(screen.queryByText("Demo · read-only")).not.toBeInTheDocument();
  expect((await screen.findAllByRole("button", { name: "Add item" })).length).toBeGreaterThan(0);
});

// User role restored
test("a stored user session comes back as a user", async () => {
  signedIn("user");
  location.hash = "#config";
  render(<App api={fakeApi()} />);
  expect(await screen.findByRole("tab", { name: "Fridge area" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Debug" })).not.toBeInTheDocument();
  location.hash = "";
});
