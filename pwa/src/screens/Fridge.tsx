import { ChevronDown, ChevronRight, Minus, Plus, Refrigerator, Snowflake } from "lucide-react";
import { useCallback, useState, type FormEvent } from "react";
import type { Item } from "../api/types";
import { useApp } from "../AppContext";
import { EmptyState } from "../components/EmptyState";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { ago, plural, titleCase } from "../format";
import { itemIcon } from "../itemIcon";
import { useLoad } from "../useLoad";

export function Fridge() {
  const { api, report, go, role } = useApp();
  const canEdit = role === "owner";
  const { data: inventory, setData: setInventory, failed } = useLoad(
    useCallback(() => api.inventory(), [api]),
    10_000,
  );
  const [editing, setEditing] = useState<Item | null>(null);

  if (!inventory) return failed ? <NoData /> : <Skeleton />;

  const inStock = inventory.items.filter((i) => i.quantity > 0);
  const outOf = inventory.items.filter((i) => i.quantity === 0);
  const groups = new Map<string, Item[]>();
  for (const item of inStock) groups.set(item.category, [...(groups.get(item.category) ?? []), item]);

  return (
    <div className="space-y-5">
      <Summary
        inStock={inStock.length}
        lastChange={latest(inventory.items)}
        pending={inventory.pending_count}
        onReview={() => go("review")}
      />

      {inStock.length === 0 && outOf.length === 0 && (
        <EmptyState
          Icon={Refrigerator}
          title="Your fridge looks empty."
          hint="Items appear here after the next door opening."
        />
      )}

      {[...groups].map(([category, items]) => (
        <section key={category} aria-labelledby={`cat-${category}`}>
          <h2
            id={`cat-${category}`}
            className="mb-2 px-1 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400"
          >
            {titleCase(category)}
          </h2>
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl bg-white shadow-sm shadow-slate-900/5 ring-1 ring-slate-200 dark:divide-slate-800 dark:bg-slate-900 dark:shadow-none dark:ring-slate-800">
            {items.map((item) => (
              <li key={item.key}>
                <ItemRow item={item} onEdit={canEdit ? () => setEditing(item) : undefined} />
              </li>
            ))}
          </ul>
        </section>
      ))}

      {outOf.length > 0 && (
        <details
          aria-label={`Out of (${outOf.length})`}
          role="group"
          className="group overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
        >
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between px-4 text-sm font-medium text-slate-600 dark:text-slate-300">
            Out of ({outOf.length})
            <ChevronDown aria-hidden className="size-4 transition group-open:rotate-180" />
          </summary>
          <ul className="divide-y divide-slate-100 border-t border-slate-100 dark:divide-slate-800 dark:border-slate-800">
            {outOf.map((item) => (
              <li key={item.key}>
                <ItemRow item={item} onEdit={canEdit ? () => setEditing(item) : undefined} />
              </li>
            ))}
          </ul>
        </details>
      )}

      {editing && (
        <QuantityEditor
          item={editing}
          onClose={() => setEditing(null)}
          onSave={async (quantity) => {
            try {
              setInventory(await api.setQuantity(editing.key, quantity));
              setEditing(null);
            } catch (err) {
              report(err);
            }
          }}
        />
      )}
    </div>
  );
}

function Summary({
  inStock,
  lastChange,
  pending,
  onReview,
}: {
  inStock: number;
  lastChange: string | null;
  pending: number;
  onReview: () => void;
}) {
  return (
    <section
      aria-label="Fridge summary"
      className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-500 to-brand-800 p-5 text-white shadow-lg shadow-brand-900/20"
    >
      <Snowflake aria-hidden className="absolute -top-6 -right-6 size-36 text-white/10" strokeWidth={1.25} />
      <p className="text-4xl font-bold tracking-tight tabular-nums">{inStock} in stock</p>
      {lastChange && <p className="mt-1 text-sm text-brand-50/85">Last change {ago(lastChange)}</p>}
      {pending > 0 && (
        <a
          href="#review"
          onClick={(e) => {
            e.preventDefault();
            onReview();
          }}
          className="relative mt-4 flex min-h-12 items-center justify-between gap-3 rounded-2xl bg-white/95 px-4 py-3 text-sm font-semibold text-warm-900 shadow-sm transition active:scale-[0.98] dark:bg-slate-950/80 dark:text-warm-200"
        >
          <span className="flex items-center gap-2.5">
            <span aria-hidden className="size-2.5 animate-pulse rounded-full bg-warm-500" />
            {plural(pending, "item")} to confirm
          </span>
          <ChevronRight aria-hidden className="size-4" />
        </a>
      )}
    </section>
  );
}

function latest(items: Item[]): string | null {
  let best: string | null = null;
  for (const i of items) {
    if (i.last_changed_at && (!best || Date.parse(i.last_changed_at) > Date.parse(best))) best = i.last_changed_at;
  }
  return best;
}

function ItemRow({ item, onEdit }: { item: Item; onEdit?: () => void }) {
  const icon = itemIcon(item.name, item.category);
  const out = item.quantity === 0;
  const content = (
    <>
      <span
        aria-hidden
        data-icon={icon}
        className={`grid size-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-2xl dark:bg-brand-950/60 ${out ? "opacity-50 grayscale" : ""}`}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block truncate font-semibold ${out ? "text-slate-500 dark:text-slate-400" : ""}`}>
          {item.name}
        </span>
        <span className="block text-xs text-slate-500 dark:text-slate-400">{ago(item.last_changed_at)}</span>
      </span>
      <span
        className={`shrink-0 rounded-full px-2.5 py-0.5 text-base font-bold tabular-nums ${
          out
            ? "text-slate-400"
            : "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100"
        }`}
      >
        ×{item.quantity}
      </span>
    </>
  );
  const cls = "flex min-h-16 w-full items-center gap-3 px-3 py-2.5 text-left";
  return onEdit ? (
    <button
      type="button"
      onClick={onEdit}
      className={`${cls} transition hover:bg-slate-50 active:bg-slate-100 dark:hover:bg-slate-800/60 dark:active:bg-slate-800`}
    >
      {content}
    </button>
  ) : (
    <div className={cls}>{content}</div>
  );
}

function QuantityEditor({
  item,
  onClose,
  onSave,
}: {
  item: Item;
  onClose: () => void;
  onSave: (quantity: number) => Promise<void>;
}) {
  const [value, setValue] = useState(String(item.quantity));
  const [busy, setBusy] = useState(false);
  const quantity = Number(value);
  const valid = value !== "" && Number.isInteger(quantity) && quantity >= 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    await onSave(quantity);
    setBusy(false);
  }

  const step = (delta: number) => setValue(String(Math.max(0, (valid ? quantity : 0) + delta)));
  const stepper =
    "grid size-12 place-items-center rounded-xl bg-slate-100 text-slate-700 transition hover:bg-slate-200 active:scale-95 dark:bg-slate-800 dark:text-slate-200";

  return (
    <Sheet title={item.name} onClose={onClose}>
      <form onSubmit={submit}>
        <label htmlFor="quantity" className="mb-2 block text-sm font-medium">
          Quantity
        </label>
        <div className="flex items-center gap-3">
          <button type="button" aria-label="One less" onClick={() => step(-1)} className={stepper}>
            <Minus aria-hidden className="size-5" />
          </button>
          <input
            id="quantity"
            inputMode="numeric"
            value={value}
            onChange={(e) => setValue(e.target.value.replace(/[^0-9]/g, ""))}
            className="h-12 w-full rounded-xl border border-slate-300 bg-white text-center text-xl font-semibold tabular-nums outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-950"
          />
          <button type="button" aria-label="One more" onClick={() => step(1)} className={stepper}>
            <Plus aria-hidden className="size-5" />
          </button>
        </div>
        <button
          type="submit"
          disabled={!valid || busy}
          className="mt-5 h-12 w-full rounded-xl bg-brand-600 font-semibold text-white transition hover:bg-brand-700 active:scale-[0.98] disabled:opacity-50"
        >
          Save
        </button>
      </form>
    </Sheet>
  );
}

function Skeleton() {
  return (
    <div aria-hidden data-testid="loading" className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className={`animate-pulse rounded-2xl bg-slate-200/70 dark:bg-slate-800 ${i === 0 ? "h-28" : "h-16"}`} />
      ))}
    </div>
  );
}
