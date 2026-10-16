import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { fakeApi, signedIn } from "./test-utils";

// Sign out
test.each(["owner", "user", "viewer"] as const)("a signed-in %s can sign out", async (role) => {
  signedIn(role);
  location.hash = "";
  const api = fakeApi();
  render(<App api={api} />);
  expect(await screen.findByRole("heading", { name: "Fridge" })).toBeInTheDocument();
  const calls = Object.values(api).map((fn) => (fn as ReturnType<typeof vi.fn>).mock.calls.length);
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
  for (const key of ["fridgesense.token", "fridgesense.role", "fridgesense.expires"]) {
    expect(localStorage.getItem(key)).toBeNull();
  }
  expect(Object.values(api).map((fn) => (fn as ReturnType<typeof vi.fn>).mock.calls.length)).toEqual(calls);
});

// Signed out stays signed out
test("after signing out, a reload shows the passcode screen", async () => {
  signedIn();
  location.hash = "";
  const { unmount } = render(<App api={fakeApi()} />);
  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  unmount();
  const api = fakeApi();
  render(<App api={api} />);
  expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
  expect(api.inventory).not.toHaveBeenCalled();
});
