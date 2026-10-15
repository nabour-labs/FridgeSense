import { render, screen } from "@testing-library/react";
import App from "./App";
import { fakeApi, signedIn } from "./test-utils";

// Empty lists keep their messages: the default fake API answers 200 with empty lists.
test.each([
  ["fridge", "Your fridge looks empty."],
  ["activity", "No door openings on this day."],
  ["review", "Everything is confirmed."],
])("an empty %s keeps its message, not No Data", async (tab, message) => {
  signedIn();
  location.hash = `#${tab}`;
  render(<App api={fakeApi()} />);
  expect(await screen.findByText(message)).toBeInTheDocument();
  expect(screen.queryByText("No Data")).not.toBeInTheDocument();
});

test("empty stats show zeros, not No Data", async () => {
  signedIn();
  location.hash = "#stats";
  render(<App api={fakeApi()} />);
  expect(await screen.findByText("Today")).toBeInTheDocument();
  expect(screen.queryByText("No Data")).not.toBeInTheDocument();
  expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
});
