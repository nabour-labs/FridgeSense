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
  /** Links to up to 2 stills that show this change (door event listings only). */
  proof?: string[];
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
  /** The open-span clip (link ending in `#t=start,end`); null for viewers and when there is none. */
  clip: string | null;
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

export interface LiveSession {
  /** SDP answer from the camera. */
  answer: string;
  session_id: string;
  /** The camera ends the session after this many seconds. */
  max_seconds: number;
}

export interface StatusChange {
  online: boolean;
  at: string;
  source: "webhook" | "poll";
}

/** The connected camera as Ring reports it, with its recorded online/offline history.
 * Detail fields are null when Ring did not report them; `ring` is "unavailable" when Ring
 * could not be reached and only the saved name and history are shown. */
export interface CameraInfo {
  device_id: string;
  name: string;
  image_url: string | null;
  manufacturer: string;
  online: boolean | null;
  video: { codecs: string[]; ratio: string | null; max_resolution: number | null; supported_resolutions: number[] } | null;
  image_enhancements: { name: string; on: boolean | null }[] | null;
  motion_detection: boolean | null;
  e2e_encryption: boolean | null;
  location: Record<string, string> | null;
  /** Newest first, last 30 days. */
  history: StatusChange[];
  uptime: { window_days: number; percent: number | null; since: string | null };
  checked_at: string;
  ring?: "unavailable";
  monitoring: Monitoring;
}

/** Whether FridgeSense records door openings for the camera; `since` is when this state began. */
export interface Monitoring {
  paused: boolean;
  since: string | null;
}

export interface Snapshot {
  /** Base64 JPEG, faces blurred. */
  image: string;
  captured_at: string;
}

export type DoorStatus = "open" | "closed";
export type DoorFeature = "blue" | "color" | "brightness" | "change";
/** Where a door zone's or reference's picture came from: a recorded clip, or the live view. */
export type PictureSource = "clip" | "live";

/** A named box around a door or drawer; setup makes one rule per zone. */
export interface DoorZone {
  id: string;
  name: string;
  box: Box;
  /** How many open and closed references it has. */
  open: number;
  closed: number;
  source: PictureSource;
}

/** A camera snapshot of one door zone, labeled open or closed. */
export interface DoorReference {
  id: string;
  zone_id: string;
  /** Base64 JPEG. */
  image: string;
  /** Its zone's current box. */
  box: Box;
  status: DoorStatus;
  /** The value of its zone's chosen feature, or null before setup. */
  score: number | null;
  created_at: string;
  source: PictureSource;
}

export interface SetupZone extends Box {
  /** The door zone it was made from (null for a setup run before zones existed). */
  id?: string | null;
  name?: string | null;
  feature: DoorFeature;
  direction: "above" | "below";
  threshold: number;
  margin: number;
}

export interface DoorSetup {
  device_id: string;
  zones: DoorZone[];
  references: DoorReference[];
  setup: {
    zones: SetupZone[];
    ran_at: string;
    stale: boolean;
    /** When the rules were last re-tuned from recent openings, and from how many samples. */
    tuned_at?: string | null;
    tuned_from?: number | null;
  } | null;
  /** How far the camera has shifted since setup (fractions of the frame); null before setup. */
  alignment?: Alignment | null;
  defaults: { zones: Box[]; threshold: number };
}

export interface Alignment {
  dx: number;
  dy: number;
  error: number | null;
  failures: number;
  moved: boolean;
  moved_at: string | null;
  last_moved_at: string | null;
  checked_at: string | null;
}

export type SetupWarning =
  | { code: "monitoring_paused"; message: string; since: string }
  | { code: "motion_detection_off" | "door_setup_missing" | "door_setup_mismatch" | "needs_relink"; message: string }
  | { code: "camera_moved"; message: string; since: string; update: ("door_references" | "fridge_area")[] }
  | { code: "privacy_mask_changed"; message: string; since: string; zones: string[] };

export interface WarningsBody {
  warnings: SetupWarning[];
  checked_at: string;
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

/** One household day's LLM totals; input counts cached input too. */
export interface UsageTotals {
  day: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  usd: number;
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

/** The owner's face-blur setting. */
export interface FaceBlur {
  enabled: boolean;
}
