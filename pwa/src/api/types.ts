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
