import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** A big icon on a tinted circle, a title, a hint and an optional action below. */
export function EmptyState({
  Icon,
  title,
  hint,
  children,
}: {
  Icon: LucideIcon;
  title: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-3xl bg-white px-6 py-12 text-center ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
      <span className="relative mb-4 grid size-20 place-items-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-950/70 dark:text-brand-300">
        <span aria-hidden className="absolute inset-2 rounded-full bg-brand-100/80 dark:bg-brand-900/50" />
        <Icon aria-hidden className="relative size-9" strokeWidth={1.75} />
      </span>
      <p className="font-semibold">{title}</p>
      {hint && <p className="mt-1 max-w-64 text-sm text-slate-500 dark:text-slate-400">{hint}</p>}
      {children && <div className="mt-5">{children}</div>}
    </div>
  );
}
