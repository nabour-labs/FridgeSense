/** `owner` is the admin (Debug too), `user` has full access without Debug, `viewer` is read-only. */
export type Role = "owner" | "user" | "viewer";

export interface Session {
  token: string;
  expires_at: string;
  role: Role;
}

export interface Item {
  key: string;
  name: string;
  category: string;
  quantity: number;
  last_changed_at: string | null;
}

export interface Inventory {
  items: Item[];
  pending_count: number;
}

export interface Change {
  item: string;
  name?: string;
  category: string;
  direction: "added" | "removed";
  quantity: number;
  confidence: number;
  applied?: boolean;
  rejected?: boolean;
}

export interface DoorEvent {
  id: string;
  opened_at: string;
  closed_at: string;
  duration_s: number;
  status: "analyzing" | "done" | "analysis_failed" | "no_media";
  changes: Change[];
  pending_count: number;
  stills: string[];
}

export interface EventPage {
  events: DoorEvent[];
  /** Pass as `cursor` for the next, older page; null on the last page. */
  next: string | null;
}

export interface Pending {
  id: string;
  door_event_id: string | null;
  item: string;
  category: string;
  direction: "added" | "removed";
  quantity: number;
  confidence: number;
  opened_at: string;
}

export type AskIntent =
  | "agent"
  | "find_item"
  | "get_inventory"
  | "fridge_activity"
  | "last_opened"
  | "unknown";

/** A fridge question's answer: the sentence to speak plus the structured result. Assistant
 * answers (source "agent") have intent "agent" and data `{ tools: [...] }`, the MCP tools it
 * called; keyword answers have the matching tool's result. `audio` is base64 MP3 or null. */
export interface AskResult {
  intent: AskIntent;
  answer: string;
  data: Record<string, unknown> | null;
  source: "agent" | "keywords";
  audio: string | null;
}

/** A photo of an item from this fridge, sent to the analysis with its annotation. */
export interface Reference {
  id: string;
  annotation: string;
  /** Base64 JPEG. */
  image: string;
  created_at: string;
}

export interface Config {
  instructions: string;
  references: Reference[];
}

/** A box in fractions of an image. */
export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Snapshot {
  /** Base64 JPEG, faces blurred. */
  image: string;
  captured_at: string;
}

export type DoorStatus = "open" | "closed";
export type DoorFeature = "color" | "brightness" | "change";

/** A camera snapshot with one box around a door or drawer, labeled open or closed. */
export interface DoorReference {
  id: string;
  /** Base64 JPEG. */
  image: string;
  box: Box;
  status: DoorStatus;
  /** The value of its zone's chosen feature, or null before setup. */
  score: number | null;
  created_at: string;
}

export interface SetupZone extends Box {
  feature: DoorFeature;
  direction: "above" | "below";
  threshold: number;
  margin: number;
}

export interface DoorSetup {
  device_id: string;
  references: DoorReference[];
  setup: { zones: SetupZone[]; ran_at: string; stale: boolean } | null;
  defaults: { zones: Box[]; threshold: number };
}

/** The owner's box around the fridge, drawn on a camera snapshot. */
export interface FridgeAreaBody {
  device_id: string;
  /** `image` is a base64 JPEG; `box` is in fractions of it. */
  area: { image: string; box: Box; updated_at: string } | null;
}

export type MotionOutcome = "door_open" | "not_door" | "no_media" | "duplicate";

export interface NovaTotals {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  usd: number;
  latency_ms: number;
}

/** One motion the pipeline traced, as listed on the Debug tab. */
export interface DebugMotion {
  id: string;
  device_id: string;
  /** The motion window's start. */
  at: string;
  outcome: MotionOutcome;
  /** The still and zone furthest past (or closest to) its threshold; null with no stills. */
  best: { value: number; zone: number; feature: DoorFeature; threshold: number } | null;
  stills_downloaded: number;
  door_event_id: string | null;
  nova: NovaTotals;
}

export interface MotionPage {
  motions: DebugMotion[];
  next: string | null;
}

export interface ZoneScore {
  zone: number;
  value: number;
  threshold: number;
  open: boolean;
}

/** A still the door check asked for: its link and scores, or why it is missing. */
export interface TracedStill {
  n: number;
  at_ms: number;
  url: string | null;
  missing_status: number | null;
  zones: ZoneScore[];
  best_zone: number | null;
  open: boolean | null;
}

export interface TracedZone {
  zone: number;
  box: Box;
  feature: DoorFeature;
  direction: "above" | "below";
  threshold: number;
  margin: number | null;
  baseline_url: string | null;
}

export interface TracedDoorReference {
  id: string;
  status: DoorStatus;
  box: Box;
  created_at: string;
  url: string | null;
}

export interface DoorTrace {
  window: { start_ms: number; end_ms: number; ring_event_id: string | null };
  outcome: MotionOutcome;
  door_sk: string | null;
  opened_at: string | null;
  closed_at: string | null;
  rule: {
    source: "setup" | "default";
    ran_at: string | null;
    zones: TracedZone[];
    references: TracedDoorReference[];
  };
  stills: TracedStill[];
  open_span: number[];
  picked: number[];
  stored_urls: string[];
}

export type RequestBlock =
  | { type: "text"; text: string }
  | { type: "cache_point" }
  | { type: "image"; role: "reference" | "still"; n: number; url: string | null };

/** One Converse attempt: what was sent, what came back, what it cost and took. */
export interface NovaCall {
  attempt: number;
  run_ms: number;
  model_id: string;
  outcome: "ok" | "invalid" | "error";
  request: { content: RequestBlock[]; inferenceConfig: unknown; toolConfig: unknown };
  response: { output?: unknown; stopReason?: string; usage?: unknown; metrics?: unknown } | null;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  usd: number;
  latency_ms: number | null;
  wall_ms: number;
  error_code: string | null;
}

export interface MotionTrace extends Omit<DebugMotion, "nova"> {
  nova_totals: NovaTotals;
  door: DoorTrace;
  nova: NovaCall[];
}
