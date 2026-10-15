import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

export interface Option {
  value: string;
  label: string;
}

/** A styled select-only combobox (WAI-ARIA pattern), used instead of the native <select> popup. */
export function Select({
  id,
  value,
  onChange,
  options,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly Option[];
}) {
  const listId = useId();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [upward, setUpward] = useState(false);
  const selected = Math.max(0, options.findIndex((o) => o.value === value));
  const [active, setActive] = useState(selected);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => root.current?.contains(e.target as Node) || setOpen(false);
    addEventListener("pointerdown", onDown);
    return () => removeEventListener("pointerdown", onDown);
  }, [open]);

  useEffect(() => {
    if (open) list.current?.children[active]?.scrollIntoView?.({ block: "nearest" });
  }, [open, active]);

  function show() {
    // Open upward when the list would run off the bottom of the screen (the sheet sits there on phones).
    const rect = button.current?.getBoundingClientRect();
    if (rect) setUpward(innerHeight - rect.bottom < 300 && rect.top > innerHeight - rect.bottom);
    setActive(selected);
    setOpen(true);
  }

  function pick(i: number) {
    onChange(options[i].value);
    setOpen(false);
    button.current?.focus();
  }

  function onKeyDown(e: KeyboardEvent) {
    const last = options.length - 1;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        show();
      }
      return;
    }
    const move = (i: number) => {
      e.preventDefault();
      setActive(Math.min(last, Math.max(0, i)));
    };
    if (e.key === "ArrowDown") move(active + 1);
    else if (e.key === "ArrowUp") move(active - 1);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(last);
    else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick(active);
    } else if (e.key === "Escape") {
      // Keep the surrounding sheet open: Escape only closes the list.
      e.stopPropagation();
      setOpen(false);
    } else if (e.key === "Tab") setOpen(false);
    else if (e.key.length === 1) {
      const i = options.findIndex((o) => o.label.toLowerCase().startsWith(e.key.toLowerCase()));
      if (i >= 0) move(i);
    }
  }

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKeyDown}
        className={`flex h-12 w-full items-center justify-between gap-3 rounded-xl border bg-white px-4 text-left outline-none transition dark:bg-slate-950 ${
          open
            ? "border-brand-500 ring-4 ring-brand-500/15"
            : "border-slate-300 focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700"
        }`}
      >
        <span className="truncate">{options[selected]?.label}</span>
        <ChevronDown aria-hidden className={`size-5 shrink-0 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul
          ref={list}
          id={listId}
          role="listbox"
          aria-labelledby={id}
          // Keep focus on the button so its keyboard handling and aria-activedescendant keep working.
          onMouseDown={(e) => e.preventDefault()}
          className={`absolute inset-x-0 z-10 max-h-72 animate-fade-in overflow-y-auto overscroll-contain rounded-2xl bg-white p-1.5 shadow-xl shadow-slate-900/10 ring-1 ring-slate-200 dark:bg-slate-900 dark:shadow-black/40 dark:ring-slate-700 ${
            upward ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === selected}
              onClick={() => pick(i)}
              onPointerMove={() => setActive(i)}
              className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-xl px-3 text-sm ${
                i === active ? "bg-slate-100 dark:bg-slate-800" : ""
              } ${i === selected ? "font-semibold text-brand-700 dark:text-brand-300" : ""}`}
            >
              {o.label}
              {i === selected && <Check aria-hidden className="size-4 shrink-0" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
