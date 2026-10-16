export type Role = "owner" | "viewer";

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
