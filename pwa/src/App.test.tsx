import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { ApiError, Offline, Unauthorized } from "./api/client";
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

// Missing camera is quiet
test("a 409 no camera linked shows no error notice", async () => {
  vi.useFakeTimers();
  try {
    signedIn();
    location.hash = "";
    const api = fakeApi({ inventory: vi.fn().mockRejectedValue(new ApiError(409)) });
    render(<App api={api} />);
    for (let i = 0; i < 2; i++) await act(async () => void vi.advanceTimersByTime(10_000));
    expect(api.inventory).toHaveBeenCalledTimes(3);
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

// Other errors still notify
test("other API errors still show Something went wrong", async () => {
  signedIn();
  location.hash = "";
  vi.spyOn(console, "error").mockImplementation(() => {});
  const api = fakeApi({ inventory: vi.fn().mockRejectedValue(new ApiError(500)) });
  render(<App api={api} />);
  expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
});

// Opened after 24 hours
test("a session past its expiry shows the passcode screen and loads nothing", () => {
  signedIn("owner", Date.now() - 1);
  const api = fakeApi();
  render(<App api={api} />);
  expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
  expect(api.inventory).not.toHaveBeenCalled();
  expect(localStorage.getItem("fridgesense.token")).toBeNull();
});

// Expires while open
test("the passcode screen returns within 60 s of expiry, even offline", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    signedIn("owner", Date.now() + 5_000);
    location.hash = "";
    const api = fakeApi({ inventory: vi.fn().mockRejectedValue(new Offline("x")) });
    render(<App api={api} />);
    expect(screen.queryByLabelText("Passcode")).not.toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(screen.getByLabelText("Passcode")).toBeInTheDocument();
    expect(localStorage.getItem("fridgesense.token")).toBeNull();
  } finally {
    vi.useRealTimers();
  }
});

// Open config
test("the header gear opens Config and loads it", async () => {
  signedIn();
  location.hash = "";
  const api = fakeApi();
  render(<App api={api} />);
  await userEvent.click(screen.getByRole("link", { name: "Config" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Config" })).toBeInTheDocument();
  expect(location.hash).toBe("#config");
  expect(api.config).toHaveBeenCalled();
  expect(await screen.findByRole("region", { name: "Reference images" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Custom instructions" })).toBeInTheDocument();
});

// Open the detection tab by link
test("#config/doors opens Config on the detection tab", async () => {
  signedIn();
  location.hash = "#config/doors";
  const api = fakeApi();
  render(<App api={api} />);
  expect(await screen.findByRole("heading", { level: 1, name: "Config" })).toBeInTheDocument();
  expect(await screen.findByRole("tab", { name: "Open/close detection", selected: true })).toBeInTheDocument();
  expect(api.doorCalibration).toHaveBeenCalled();
  location.hash = "";
});
