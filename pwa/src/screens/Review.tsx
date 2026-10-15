import { Check, CheckCheck, Pencil, X } from "lucide-react";
import { useCallback, useState, type FormEvent } from "react";
import type { Pending } from "../api/types";
import { useApp } from "../AppContext";
import { EmptyState } from "../components/EmptyState";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { changeLabel, clock, dayLabel } from "../format";
import { useLoad } from "../useLoad";

export function Review() {
  const { api, report, role } = useApp();
  const canAct = role === "owner";
  const { data: items, setData: setItems, failed } = useLoad(
    useCallback(() => api.pending().then((r) => r.pending), [api]),
    10_000,
  );
  const [editing, setEditing] = useState<Pending | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function act(p: Pending, action: () => Promise<unknown>) {
    setBusy(p.id);
    try {
      await action();
      setItems((current) => current?.filter((x) => x.id !== p.id) ?? null);
      setEditing(null);
    } catch (err) {
      report(err);
    } finally {
      setBusy(null);
    }
  }

  if (!items) {
    if (failed) return <NoData />;
    return <div aria-hidden data-testid="loading" className="h-32 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }
  if (items.length === 0) {
    return (
      <EmptyState
        Icon={CheckCheck}
        title="Everything is confirmed."
        hint="Changes the camera is unsure about show up here."
      />
    );
  }

  return (
    <div className="space-y-3">
      <p className="px-1 text-sm text-slate-500 dark:text-slate-400">
        {canAct
          ? "The camera wasn't sure about these. Confirm, fix or dismiss each one."
          : "The camera wasn't sure about these. The owner confirms them."}
      </p>
      <ul className="space-y-3">
        {items.map((p) => (
          <li key={p.id}>
            <article className="rounded-2xl bg-white p-4 shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-lg font-bold">{changeLabel(p)}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {dayLabel(p.opened_at)} · {clock(p.opened_at)}
                  </p>
                </div>
                <span className="shrink-0 pt-1 text-xs font-semibold tabular-nums text-slate-600 dark:text-slate-300">
                  {Math.round(p.confidence * 100)}% sure
                </span>
              </div>
              <ConfidenceMeter confidence={p.confidence} />
              {canAct && (
              <div className="mt-4 grid grid-cols-3 gap-2">
                <ActionButton
                  label="Confirm"
                  Icon={Check}
                  tone="primary"
                  disabled={busy === p.id}
                  onClick={() => act(p, () => api.confirm(p.id, undefined))}
                />
                <ActionButton label="Edit" Icon={Pencil} disabled={busy === p.id} onClick={() => setEditing(p)} />
                <ActionButton
                  label="Not right"
                  Icon={X}
                  disabled={busy === p.id}
                  onClick={() => act(p, () => api.reject(p.id))}
                />
              </div>
              )}
            </article>
          </li>
        ))}
      </ul>
      {editing && (
        <EditSheet
          pending={editing}
          onClose={() => setEditing(null)}
          onConfirm={(item, quantity) => act(editing, () => api.confirm(editing.id, { item, quantity }))}
        />
      )}
    </div>
  );
}

const METER_TONES = { low: "bg-rose-500", medium: "bg-warm-500", high: "bg-brand-500" } as const;

function ConfidenceMeter({ confidence }: { confidence: number }) {
  const value = Math.round(confidence * 100);
  const tone = confidence < 0.5 ? "low" : confidence < 0.7 ? "medium" : "high";
  return (
    <div
      role="meter"
      aria-label="Confidence"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      data-tone={tone}
      className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
    >
      <div className={`h-full rounded-full ${METER_TONES[tone]}`} style={{ width: `${value}%` }} />
    </div>
  );
}

function ActionButton({
  label,
  Icon,
  onClick,
  disabled,
  tone,
}: {
  label: string;
  Icon: typeof Check;
  onClick: () => void;
  disabled?: boolean;
  tone?: "primary";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-h-11 items-center justify-center gap-1.5 rounded-xl text-sm font-semibold transition active:scale-[0.97] disabled:opacity-50 ${
        tone === "primary"
          ? "bg-brand-600 text-white shadow-sm shadow-brand-700/30 hover:bg-brand-700"
          : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200"
      }`}
    >
      <Icon aria-hidden className="size-4" />
      {label}
    </button>
  );
}

function EditSheet({
  pending,
  onClose,
  onConfirm,
}: {
  pending: Pending;
  onClose: () => void;
  onConfirm: (item: string, quantity: number) => void;
}) {
  const [item, setItem] = useState(pending.item);
  const [qty, setQty] = useState(String(pending.quantity));
  const quantity = Number(qty);
  const valid = item.trim() !== "" && Number.isInteger(quantity) && quantity >= 1;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (valid) onConfirm(item.trim(), quantity);
  }

  const input =
    "h-12 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-base outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-950";
  return (
    <Sheet title={pending.direction === "added" ? "What was put in?" : "What was taken out?"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="edit-item" className="mb-1.5 block text-sm font-medium">
            Item
          </label>
          <input id="edit-item" value={item} onChange={(e) => setItem(e.target.value)} className={input} />
        </div>
        <div>
          <label htmlFor="edit-qty" className="mb-1.5 block text-sm font-medium">
            Quantity
          </label>
          <input
            id="edit-qty"
            inputMode="numeric"
            value={qty}
            onChange={(e) => setQty(e.target.value.replace(/[^0-9]/g, ""))}
            className={input}
          />
        </div>
        <button
          type="submit"
          disabled={!valid}
          className="h-12 w-full rounded-xl bg-brand-600 font-semibold text-white transition hover:bg-brand-700 active:scale-[0.98] disabled:opacity-50"
        >
          Confirm
        </button>
      </form>
    </Sheet>
  );
}
