export function titleCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "just now", "5 min ago", "3 h ago", "2 d ago". */
export function ago(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "";
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86_400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86_400)} d ago`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

export function dayLabel(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((start(now) - start(d)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

/** "+ milk", "− 2 eggs" */
export function changeLabel(c: { direction: "added" | "removed"; quantity: number; item: string; name?: string }) {
  const sign = c.direction === "added" ? "+" : "−";
  return `${sign} ${c.quantity > 1 ? `${c.quantity} ` : ""}${c.name ?? c.item}`;
}
