import { render, screen } from "@testing-library/react";
import App from "./App";
import { Offline } from "./api/client";
import { fakeApi, signedIn } from "./test-utils";

// Offline shell (app part)
test("the app shows it can't reach FridgeSense instead of failing", async () => {
  signedIn();
  location.hash = "";
  render(<App api={fakeApi({ inventory: vi.fn().mockRejectedValue(new Offline()) })} />);
  expect(await screen.findByText(/Can't reach FridgeSense/)).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Screens" })).toBeInTheDocument();
});
