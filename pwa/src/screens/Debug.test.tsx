import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import type { DebugMotion, DoorTrace, MotionTrace, NovaCall, TracedStill } from "../api/types";
import { AppContext, type Api } from "../AppContext";
import { clock } from "../format";
import { fakeApi } from "../test-utils";
import { Debug } from "./Debug";

const AT = new Date(2026, 9, 16, 18, 2).toISOString();
const NO_NOVA = { calls: 0, input_tokens: 0, output_tokens: 0, usd: 0, latency_ms: 0 };

function motion(overrides: Partial<DebugMotion> = {}): DebugMotion {
  return {
    id: "abc",
    device_id: "D1",
    at: AT,
    outcome: "not_door",
    best: { value: 0.0123, zone: 1, feature: "color", threshold: 0.02 },
    stills_downloaded: 4,
    door_event_id: null,
    nova: NO_NOVA,
    ...overrides,
  };
}

function still(n: number, open: boolean, value: number, extra: Partial<TracedStill> = {}): TracedStill {
  return {
    n,
    at_ms: 1_786_715_600_000 + n * 1000,
    url: `https://s3/raw-${n}.jpg`,
    missing_status: null,
    zones: [{ zone: 1, value, threshold: 0.11, open }],
    best_zone: 1,
    open,
    ...extra,
  };
}

const ZONE = { x: 0.38, y: 0.32, width: 0.21, height: 0.3 };

function door(overrides: Partial<DoorTrace> = {}): DoorTrace {
  return {
    window: { start_ms: 1_786_715_600_000, end_ms: 1_786_715_625_000, ring_event_id: "evt" },
    outcome: "door_open",
    door_sk: "DOOR#x",
    opened_at: AT,
    closed_at: AT,
    rule: {
      source: "setup",
      ran_at: AT,
      zones: [
        {
          zone: 1,
          box: ZONE,
          feature: "change",
          direction: "above",
          threshold: 0.11,
          margin: 0.07,
          baseline_url: "https://s3/baseline-1.png",
        },
      ],
      references: [
        { id: "r1", status: "closed", box: ZONE, created_at: AT, url: "https://s3/door-ref-r1.jpg" },
        { id: "r2", status: "closed", box: ZONE, created_at: AT, url: "https://s3/door-ref-r2.jpg" },
        { id: "r3", status: "open", box: ZONE, created_at: AT, url: "https://s3/door-ref-r3.jpg" },
      ],
    },
    stills: [1, 2, 3, 4, 5, 6].map((n) => still(n, n === 3 || n === 4, n === 3 || n === 4 ? 0.15 : 0.0042)),
    open_span: [3, 4, 5],
    picked: [3, 4],
    stored_urls: [],
    ...overrides,
  };
}

function novaCall(overrides: Partial<NovaCall> = {}): NovaCall {
  return {
    attempt: 1,
    run_ms: 1,
    model_id: "us.amazon.nova-2-lite-v1:0",
    outcome: "ok",
    request: {
      content: [
        { type: "text", text: "Reference photos of items in this fridge:" },
        { type: "text", text: "Reference 1: oat milk" },
        { type: "image", role: "reference", n: 1, url: "https://s3/ref-1.jpg" },
        { type: "text", text: "Reference 2: eggs" },
        { type: "image", role: "reference", n: 2, url: "https://s3/ref-2.jpg" },
        { type: "cache_point" },
        ...[1, 2, 3, 4].flatMap((n) => [
          { type: "text" as const, text: `Image ${n} of 4` },
          { type: "image" as const, role: "still" as const, n, url: `https://s3/still-${n}.jpg` },
        ]),
        { type: "text", text: "Current inventory: [milk]" },
      ],
      inferenceConfig: { maxTokens: 1024 },
      toolConfig: {},
    },
    response: { output: { message: { content: [{ toolUse: { input: { added: [], removed: [] } } }] } }, stopReason: "tool_use" },
    input_tokens: 1180,
    output_tokens: 96,
    cache_read_tokens: 2000,
    cache_write_tokens: 0,
    usd: 0.000818,
    latency_ms: 2140,
    wall_ms: 2310,
    error_code: null,
    ...overrides,
  };
}

function trace(overrides: Partial<MotionTrace> = {}): MotionTrace {
  const { nova: _nova, ...m } = motion({ outcome: "door_open" });
  return { ...m, nova_totals: NO_NOVA, door: door(), nova: [novaCall()], ...overrides };
}

function renderDebug(api: Partial<Record<keyof Api, unknown>>) {
  const fake = fakeApi(api);
  render(
    <AppContext.Provider value={{ api: fake, role: "owner", report: vi.fn(), online: vi.fn(), go: vi.fn() }}>
      <Debug />
    </AppContext.Provider>,
  );
  return fake;
}

function list(motions: DebugMotion[]) {
  location.hash = "#config/debug";
  return renderDebug({ debugMotions: vi.fn().mockResolvedValue({ motions, next: null }) });
}

function detail(t: MotionTrace | Error) {
  location.hash = "#config/debug/abc";
  const debugMotion = t instanceof Error ? vi.fn().mockRejectedValue(t) : vi.fn().mockResolvedValue(t);
  return renderDebug({ debugMotion });
}

afterEach(() => {
  location.hash = "";
});

// Not-door row
test("a not-door motion shows its time, outcome and best score", async () => {
  list([motion()]);
  const row = await screen.findByRole("button", { name: new RegExp(clock(AT)) });
  expect(within(row).getByText(clock(AT))).toBeInTheDocument();
  expect(within(row).getByText("Not the door")).toBeInTheDocument();
  expect(within(row).getByText("0.0123 / 0.02")).toBeInTheDocument();
  expect(within(row).queryByText(/calls?$/)).not.toBeInTheDocument();
});

// Door opening row
test("a door opening shows its Nova calls, tokens, cost and latency", async () => {
  list([
    motion({
      outcome: "door_open",
      nova: { calls: 2, input_tokens: 2380, output_tokens: 186, usd: 0.00162, latency_ms: 4040 },
    }),
  ]);
  const row = await screen.findByRole("button", { name: new RegExp(clock(AT)) });
  for (const text of ["Door opening", "2 calls", "2,380 in", "186 out", "$0.0016", "4.0 s"]) {
    expect(within(row).getByText(text)).toBeInTheDocument();
  }
});

// No motions
test("an empty day says no motions were recorded", async () => {
  list([]);
  expect(await screen.findByText("No motions recorded on this day.")).toBeInTheDocument();
});

test("the list asks for today, 10 at a time", async () => {
  const api = list([]);
  await screen.findByText("No motions recorded on this day.");
  const [from, to, limit] = (api.debugMotions as ReturnType<typeof vi.fn>).mock.calls[0];
  const midnight = new Date();
  midnight.setHours(0, 0, 0, 0);
  expect(from).toEqual(midnight);
  expect(to.getTime() - from.getTime()).toBeGreaterThanOrEqual(23 * 3600_000);
  expect(limit).toBe(10);
});

// Open a motion
test("tapping a row opens that motion", async () => {
  const api = list([motion()]);
  (api.debugMotion as ReturnType<typeof vi.fn>).mockResolvedValue(trace());
  await userEvent.click(await screen.findByRole("button", { name: new RegExp(clock(AT)) }));
  expect(location.hash).toBe("#config/debug/abc");
  expect(api.debugMotion).toHaveBeenCalledWith("abc");
});

// Door section
test("the door section shows every still with its verdict and score, and the rule", async () => {
  detail(trace());
  const section = await screen.findByRole("region", { name: "Door check" });
  const stills = within(section).getAllByRole("listitem", { name: /^Still \d/ });
  expect(stills).toHaveLength(6);
  expect(stills.map((s) => within(s).getByText(/^(Open|Closed)$/).textContent)).toEqual([
    "Closed",
    "Closed",
    "Open",
    "Open",
    "Closed",
    "Closed",
  ]);
  expect(within(stills[2]).getByText("Zone 1: 0.1500 / 0.11")).toBeInTheDocument();
  expect(within(stills[0]).getByText("Zone 1: 0.0042 / 0.11")).toBeInTheDocument();
  expect(within(stills[0]).getByRole("img", { name: "Still 1" })).toHaveAttribute("src", "https://s3/raw-1.jpg");

  const rule = within(section).getByRole("region", { name: "Rule" });
  expect(within(rule).getByText("From setup")).toBeInTheDocument();
  const zone = within(rule).getByRole("listitem", { name: "Zone 1" });
  for (const text of ["change", "above", "0.11", "margin 0.07"]) {
    expect(within(zone).getByText(text)).toBeInTheDocument();
  }
  expect(within(zone).getByRole("img", { name: "Zone 1 baseline" })).toHaveAttribute("src", "https://s3/baseline-1.png");
  const refs = within(rule).getAllByRole("img", { name: /^Door reference/ });
  expect(refs).toHaveLength(3);
  expect(within(rule).getAllByText("closed")).toHaveLength(2);
  expect(within(rule).getByText("open")).toBeInTheDocument();
});

// Picked stills marked
test("stills sent to analysis are marked", async () => {
  detail(trace());
  const section = await screen.findByRole("region", { name: "Door check" });
  const marked = within(section)
    .getAllByRole("listitem", { name: /^Still \d/ })
    .filter((s) => within(s).queryByText("Sent to analysis"));
  expect(marked.map((s) => s.getAttribute("aria-label"))).toEqual(["Still 3", "Still 4"]);
});

// Missing still
test("a still that never downloaded shows why", async () => {
  const stills = door().stills;
  stills[4] = still(5, false, 0, { url: null, missing_status: 416, zones: [], best_zone: null, open: null });
  detail(trace({ door: door({ stills }) }));
  const item = await screen.findByRole("listitem", { name: "Still 5" });
  expect(within(item).getByText("Not downloaded (416)")).toBeInTheDocument();
  expect(within(item).queryByRole("img")).not.toBeInTheDocument();
});

// Default rule
test("the default rule shows no baseline or references", async () => {
  const base = door();
  detail(
    trace({
      door: door({
        rule: {
          source: "default",
          ran_at: null,
          zones: [{ ...base.rule.zones[0], feature: "color", margin: null, baseline_url: null }],
          references: [],
        },
      }),
    }),
  );
  const rule = await screen.findByRole("region", { name: "Rule" });
  expect(within(rule).getByText("Default zones")).toBeInTheDocument();
  expect(within(rule).queryByRole("img")).not.toBeInTheDocument();
});

// Missing detail
test("an expired trace says so, and Back returns to the list", async () => {
  const api = detail(new ApiError(404, "no trace"));
  expect(await screen.findByText("This trace has expired or was never recorded.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(location.hash).toBe("#config/debug");
  expect(api.debugMotions).toHaveBeenCalled();
});

// Request in order
test("a Nova call shows its request in order", async () => {
  detail(trace());
  const call = await screen.findByRole("region", { name: "Nova call 1" });
  const blocks = within(call).getAllByTestId("request-block").map((b) => b.getAttribute("data-label"));
  expect(blocks).toEqual([
    "text",
    "text",
    "Reference 1",
    "text",
    "Reference 2",
    "cache point",
    "text",
    "Still 1",
    "text",
    "Still 2",
    "text",
    "Still 3",
    "text",
    "Still 4",
    "text",
  ]);
  expect(within(call).getByText("Reference 1: oat milk")).toBeInTheDocument();
  expect(within(call).getByRole("img", { name: "Reference 1" })).toHaveAttribute("src", "https://s3/ref-1.jpg");
});

test("tapping an image in a Nova call shows it full size", async () => {
  detail(trace());
  const call = await screen.findByRole("region", { name: "Nova call 1" });
  await userEvent.click(within(call).getByRole("button", { name: "Still 2" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("img", { name: "Still 2" })).toHaveAttribute("src", "https://s3/still-2.jpg");
});

// Numbers shown
test("a Nova call shows tokens, cost and both latencies", async () => {
  detail(trace());
  const call = await screen.findByRole("region", { name: "Nova call 1" });
  for (const text of ["1,180", "96", "2,000", "0", "$0.000818", "2.14 s", "2.31 s"]) {
    expect(within(call).getByText(text)).toBeInTheDocument();
  }
  expect(within(call).getByText(/"stopReason": "tool_use"/)).toBeInTheDocument();
});

// Failed call
test("a failed call shows its error instead of a response", async () => {
  detail(
    trace({
      nova: [
        novaCall({
          outcome: "error",
          error_code: "ThrottlingException",
          response: null,
          input_tokens: 0,
          output_tokens: 0,
          cache_read_tokens: 0,
          usd: 0,
          latency_ms: null,
          wall_ms: 120,
        }),
      ],
    }),
  );
  const call = await screen.findByRole("region", { name: "Nova call 1" });
  expect(within(call).getByText("ThrottlingException")).toBeInTheDocument();
  expect(within(call).queryByText("Input tokens")).not.toBeInTheDocument();
});

// Invalid answer
test("an invalid answer is marked and shows its stop reason", async () => {
  detail(
    trace({
      nova: [
        novaCall({
          outcome: "invalid",
          response: { output: { message: { content: [{ text: "Milk." }] } }, stopReason: "end_turn" },
        }),
      ],
    }),
  );
  const call = await screen.findByRole("region", { name: "Nova call 1" });
  expect(within(call).getByText("Invalid answer")).toBeInTheDocument();
  expect(within(call).getByText("Stop reason: end_turn")).toBeInTheDocument();
  expect(within(call).getByText(/"Milk\."/)).toBeInTheDocument();
});
