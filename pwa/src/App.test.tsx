import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { Unauthorized } from "./api/client";
import { fakeApi, signedIn } from "./test-utils";

// First visit
test("first visit shows the passcode screen and loads nothing", () => {
  const api = fakeApi();
  render(<App api={api} />);
  expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  expect(api.inventory).not.toHaveBeenCalled();
});

// Successful sign-in
test("successful sign-in stores the token and shows the Fridge screen", async () => {
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.type(screen.getByLabelText("Passcode"), "open-sesame");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(api.signIn).toHaveBeenCalledWith("open-sesame");
  expect(await screen.findByRole("heading", { name: "Fridge" })).toBeInTheDocument();
  expect(localStorage.getItem("fridgesense.token")).toBe("tok");
  expect(localStorage.getItem("fridgesense.role")).toBe("owner");
});

// Wrong passcode
test("wrong passcode stays on the passcode screen", async () => {
  const api = fakeApi({ signIn: vi.fn().mockRejectedValue(new Unauthorized()) });
  render(<App api={api} />);
  await userEvent.type(screen.getByLabelText("Passcode"), "guess");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Wrong passcode")).toBeInTheDocument();
  expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
  expect(localStorage.getItem("fridgesense.token")).toBeNull();
});

// Session expired
test("a 401 while signed in returns to the passcode screen", async () => {
  signedIn();
  const api = fakeApi({ inventory: vi.fn().mockRejectedValue(new Unauthorized()) });
  render(<App api={api} />);
  expect(await screen.findByLabelText("Passcode")).toBeInTheDocument();
  await waitFor(() => expect(localStorage.getItem("fridgesense.token")).toBeNull());
});
