import { ChevronDown, Minus, Plus } from "lucide-react";
import { useCallback, useState, type FormEvent } from "react";
import type { Inventory, Item } from "../api/types";
import { useApp } from "../AppContext";
import { Sheet } from "../components/Sheet";
import { ago, plural, titleCase } from "../format";
import { usePolling } from "../usePolling";

export function Fridge() {
  const { api, report, online, go } = useApp();
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [editing, setEditing] = useState<Item | null>(null);

  const load = useCallback(() => {
    api.inventory().then((inv) => {
      setInventory(inv);
      online();
    }, report);
  }, [api, report, online]);
  usePolling(load, 10_000);

  if (!inventory) return <Skeleton />;

  const inStock = inventory.items.filter((i) => i.quantity > 0);
  const outOf = inventory.items.filter((i) => i.quantity === 0);
  const groups = new Map<string, Item[]>();
  for (const item of inStock) groups.set(item.category, [...(groups.get(item.category) ?? []), item]);

  return (
    <div className="space-y-5">
      {inventory.pending_count > 0 && (
        <a
          href="#review"
          onClick={(e) => {
            e.preventDefault();
            go("review");
          }}
          className="flex min-h-12 items-center justify-between rounded-2xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-100 dark:ring-amber-900"
        >
          <span>{plural(inventory.pending_count, "item")} to confirm</span>
          <span aria-hidden>→</span>
        </a>
      )}

      {inStock.length === 0 && outOf.length === 0 && (
        <div className="rounded-3xl border border-dashed border-slate-300 px-6 py-12 text-center dark:border-slate-700">
          <p className="font-medium">Your fridge looks empty.</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Items appear here after the next door opening.
          </p>
        </div>
      )}

      {[...groups].map(([category, items]) => (
        <section key={category} aria-labelledby={`cat-${category}`}>
          <h2
            id={`cat-${category}`}
            className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
          >
            {titleCase(category)}
          </h2>
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200 dark:divide-slate-800 dark:bg-slate-900 dark:ring-slate-800">
            {items.map((item) => (
              <li key={item.key}>
                <ItemRow item={item} onEdit={() => setEditing(item)} />
              </li>
            ))}
          </ul>
        </section>
      ))}

      {outOf.length > 0 && (
        <details
          aria-label={`Out of (${outOf.length})`}
          role="group"
          className="group rounded-2xl bg-white ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
        >
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between px-4 text-sm font-medium text-slate-600 dark:text-slate-300">
            Out of ({outOf.length})
            <ChevronDown aria-hidden className="size-4 transition group-open:rotate-180" />
          </summary>
          <ul className="divide-y divide-slate-100 border-t border-slate-100 dark:divide-slate-800 dark:border-slate-800">
            {outOf.map((item) => (
              <li key={item.key}>
                <ItemRow item={item} onEdit={() => setEditing(item)} />
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

function ItemRow({ item, onEdit }: { item: Item; onEdit?: () => void }) {
  const content = (
    <>
      <span className="min-w-0">
        <span className="block truncate font-medium">{item.name}</span>
        <span className="block text-xs text-slate-500 dark:text-slate-400">
          {ago(item.last_changed_at)}
        </span>
      </span>
      <span
        className={`shrink-0 text-lg font-semibold tabular-nums ${
          item.quantity === 0 ? "text-slate-400" : "text-slate-900 dark:text-slate-100"
        }`}
      >
        ×{item.quantity}
      </span>
    </>
  );
  const cls = "flex min-h-14 w-full items-center justify-between gap-3 px-4 py-2 text-left";
  return onEdit ? (
    <button type="button" onClick={onEdit} className={`${cls} hover:bg-slate-50 dark:hover:bg-slate-800/60`}>
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
    "grid size-12 place-items-center rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200";

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
            className="h-12 w-full rounded-xl border border-slate-300 bg-white text-center text-xl font-semibold tabular-nums outline-none focus:border-sky-500 dark:border-slate-700 dark:bg-slate-950"
          />
          <button type="button" aria-label="One more" onClick={() => step(1)} className={stepper}>
            <Plus aria-hidden className="size-5" />
          </button>
        </div>
        <button
          type="submit"
          disabled={!valid || busy}
          className="mt-5 h-12 w-full rounded-xl bg-sky-600 font-semibold text-white hover:bg-sky-700 disabled:opacity-50"
        >
          Save
        </button>
      </form>
    </Sheet>
  );
}

function Skeleton() {
  return (
    <div aria-hidden className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-14 animate-pulse rounded-2xl bg-slate-200/70 dark:bg-slate-800" />
      ))}
    </div>
  );
}
