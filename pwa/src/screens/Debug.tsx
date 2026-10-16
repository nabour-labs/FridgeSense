import { ChevronLeft, ChevronRight, Footprints, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import type {
  DebugMotion,
  DoorTrace,
  MotionOutcome,
  MotionPage,
  MotionTrace,
  NovaCall,
  RequestBlock,
  TracedStill,
} from "../api/types";
import { useApp } from "../AppContext";
import { EmptyState } from "../components/EmptyState";
import { ImageMarkup } from "../components/ImageMarkup";
import { NoData } from "../components/NoData";
import { Sheet } from "../components/Sheet";
import { clock } from "../format";
import { boxShape } from "../shapes";
import { CARD, HEADING } from "./configStyles";

const PAGE_SIZE = 10;
const LIST_HASH = "#config/debug";

const OUTCOMES: Record<MotionOutcome, string> = {
  door_open: "Door opening",
  not_door: "Not the door",
  no_media: "No stills",
  duplicate: "Duplicate",
};

const whole = (n: number) => n.toLocaleString("en-US");
const seconds = (ms: number, places: number) => `${(ms / 1000).toFixed(places)} s`;
const score = (n: number) => n.toFixed(4);

function startOfDay(d: Date, plusDays = 0): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + plusDays);
}

function dateValue(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function motionFromHash(): string | null {
  const id = location.hash.startsWith(`${LIST_HASH}/`) ? location.hash.slice(LIST_HASH.length + 1) : "";
  return id ? decodeURIComponent(id) : null;
}

/** Config → Debug: every motion the pipeline traced, and what it saw, decided and spent. */
export function Debug() {
  const [id, setId] = useState(motionFromHash);
  useEffect(() => {
    const onHash = () => setId(motionFromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);
  const open = (next: string | null) => {
    history.replaceState(null, "", next ? `${LIST_HASH}/${encodeURIComponent(next)}` : LIST_HASH);
    setId(next);
  };
  return id ? <MotionDetail key={id} id={id} onBack={() => open(null)} /> : <MotionList onOpen={open} />;
}

function MotionList({ onOpen }: { onOpen: (id: string) => void }) {
  const [day, setDay] = useState(() => startOfDay(new Date()));
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const today = dateValue(new Date());
  const pickDay = (value: string) => {
    const [y, m, d] = value.split("-").map(Number);
    if (!y || !m || !d || value > today) return;
    setDay(new Date(y, m - 1, d));
    setCursors([undefined]);
  };
  return (
    <div className="space-y-4">
      <input
        type="date"
        aria-label="Day"
        value={dateValue(day)}
        max={today}
        onChange={(e) => pickDay(e.target.value)}
        className="h-11 w-full rounded-xl border border-slate-300 bg-white px-3 font-semibold outline-none [color-scheme:light] focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-950 dark:[color-scheme:dark]"
      />
      <MotionPage
        key={`${dateValue(day)}/${cursors.at(-1) ?? ""}`}
        day={day}
        cursor={cursors.at(-1)}
        page={cursors.length}
        onOpen={onOpen}
        onOlder={(next) => setCursors([...cursors, next])}
        onNewer={() => setCursors(cursors.slice(0, -1))}
      />
    </div>
  );
}

function MotionPage({
  day,
  cursor,
  page,
  onOpen,
  onOlder,
  onNewer,
}: {
  day: Date;
  cursor: string | undefined;
  page: number;
  onOpen: (id: string) => void;
  onOlder: (next: string) => void;
  onNewer: () => void;
}) {
  const { api, report, online } = useApp();
  const [data, setData] = useState<MotionPage | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let current = true;
    api.debugMotions(day, startOfDay(day, 1), PAGE_SIZE, cursor).then(
      (page) => {
        if (!current) return;
        setData(page);
        online();
      },
      (error) => {
        if (!current) return;
        report(error);
        setFailed(true);
      },
    );
    return () => {
      current = false;
    };
  }, [api, day, cursor, report, online]);
  if (!data) {
    if (failed) return <NoData />;
    return <div aria-hidden className="h-40 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />;
  }
  const pager =
    "flex h-11 items-center gap-1 rounded-full bg-slate-100 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 active:scale-95 disabled:opacity-30 dark:bg-slate-800 dark:text-slate-200";
  return (
    <div className="space-y-4">
      {data.motions.length === 0 ? (
        <EmptyState
          Icon={Footprints}
          title="No motions recorded on this day."
          hint="Every motion the camera reports shows up here for 7 days."
        />
      ) : (
        <ol className="space-y-2">
          {data.motions.map((m) => (
            <li key={m.id}>
              <MotionRow motion={m} onOpen={() => onOpen(m.id)} />
            </li>
          ))}
        </ol>
      )}
      {(data.motions.length > 0 || page > 1) && (
        <nav aria-label="Pages" className="flex items-center justify-between">
          <button type="button" disabled={page === 1} onClick={onNewer} className={pager}>
            <ChevronLeft aria-hidden className="size-4" />
            Newer
          </button>
          <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">Page {page}</span>
          <button type="button" disabled={!data.next} onClick={() => data.next && onOlder(data.next)} className={pager}>
            Older
            <ChevronRight aria-hidden className="size-4" />
          </button>
        </nav>
      )}
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome: MotionOutcome }) {
  const tone =
    outcome === "door_open"
      ? "bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-200 dark:ring-emerald-900"
      : "bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700";
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${tone}`}>{OUTCOMES[outcome]}</span>;
}

function MotionRow({ motion, onOpen }: { motion: DebugMotion; onOpen: () => void }) {
  const { nova, best } = motion;
  const chip = "rounded-md bg-slate-100 px-1.5 py-0.5 tabular-nums dark:bg-slate-800";
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`${CARD} flex w-full flex-col gap-2 p-3 text-left transition hover:ring-brand-300 active:scale-[0.99]`}
    >
      <span className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-base font-bold tabular-nums">{clock(motion.at)}</span>
        <OutcomeBadge outcome={motion.outcome} />
      </span>
      <span className="flex flex-wrap gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
        {best && <span className={chip}>{`${score(best.value)} / ${best.threshold}`}</span>}
        {nova.calls > 0 && (
          <>
            <span className={chip}>{nova.calls === 1 ? "1 call" : `${nova.calls} calls`}</span>
            <span className={chip}>{`${whole(nova.input_tokens)} in`}</span>
            <span className={chip}>{`${whole(nova.output_tokens)} out`}</span>
            <span className={chip}>{`$${nova.usd.toFixed(4)}`}</span>
            <span className={chip}>{seconds(nova.latency_ms, 1)}</span>
          </>
        )}
      </span>
    </button>
  );
}

type Viewing = { src: string; title: string };

function MotionDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const { api, report } = useApp();
  const [trace, setTrace] = useState<MotionTrace | null>(null);
  const [missing, setMissing] = useState(false);
  const [failed, setFailed] = useState(false);
  const [viewing, setViewing] = useState<Viewing | null>(null);
  const load = useCallback(() => {
    api.debugMotion(id).then(setTrace, (error) => {
      if (error instanceof ApiError && error.status === 404) return setMissing(true);
      report(error);
      setFailed(true);
    });
  }, [api, id, report]);
  useEffect(load, [load]);

  const back = (
    <button
      type="button"
      onClick={onBack}
      className="flex h-10 items-center gap-1 rounded-full bg-slate-100 px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 active:scale-95 dark:bg-slate-800 dark:text-slate-200"
    >
      <ChevronLeft aria-hidden className="size-4" />
      Back
    </button>
  );

  if (!trace) {
    return (
      <div className="space-y-4">
        {back}
        {missing ? (
          <p className="text-sm text-slate-600 dark:text-slate-300">This trace has expired or was never recorded.</p>
        ) : failed ? (
          <NoData />
        ) : (
          <div aria-hidden className="h-40 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800" />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        {back}
        <span className="flex items-center gap-2">
          <span className="text-sm font-bold tabular-nums">{clock(trace.at)}</span>
          <OutcomeBadge outcome={trace.outcome} />
          <button
            type="button"
            aria-label="Refresh"
            onClick={load}
            className="grid size-10 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 active:scale-95 dark:hover:bg-slate-800"
          >
            <RefreshCw aria-hidden className="size-4" />
          </button>
        </span>
      </div>
      <DoorSection door={trace.door} onView={setViewing} />
      {trace.nova.map((call, i) => (
        <NovaSection key={`${call.run_ms}-${call.attempt}`} call={call} index={i + 1} onView={setViewing} />
      ))}
      {viewing && (
        <Sheet title={viewing.title} onClose={() => setViewing(null)}>
          <img src={viewing.src} alt={viewing.title} className="w-full rounded-2xl bg-slate-100 object-contain dark:bg-slate-800" />
        </Sheet>
      )}
    </div>
  );
}

function DoorSection({ door, onView }: { door: DoorTrace; onView: (v: Viewing) => void }) {
  const zones = door.rule.zones.map((z) => boxShape(z.box));
  return (
    <section aria-label="Door check" className="space-y-3">
      <h2 className={HEADING}>Door check</h2>
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {door.stills.map((s) => (
          <StillCard key={s.n} still={s} picked={door.picked.includes(s.n)} zones={zones} onView={onView} />
        ))}
      </ol>
      <section aria-label="Rule" className={`${CARD} space-y-3 p-3`}>
        <p className="text-sm font-semibold">
          {door.rule.source === "setup" ? "From setup" : "Default zones"}
          {door.rule.ran_at && (
            <span className="font-normal text-slate-500 dark:text-slate-400"> · ran {new Date(door.rule.ran_at).toLocaleString()}</span>
          )}
        </p>
        <ul className="space-y-2">
          {door.rule.zones.map((z) => (
            <li key={z.zone} aria-label={`Zone ${z.zone}`} className="flex items-center gap-3 text-sm">
              {z.baseline_url && (
                <img src={z.baseline_url} alt={`Zone ${z.zone} baseline`} className="size-12 rounded-lg object-cover [image-rendering:pixelated]" />
              )}
              <span className="flex flex-wrap gap-1.5">
                <span className="font-semibold">Zone {z.zone}</span>
                <span>{z.feature}</span>
                <span>{z.direction}</span>
                <span className="tabular-nums">{z.threshold}</span>
                {z.margin !== null && <span className="text-slate-500 dark:text-slate-400">{`margin ${z.margin}`}</span>}
              </span>
            </li>
          ))}
        </ul>
        {door.rule.references.length > 0 && (
          <ul className="grid grid-cols-3 gap-2">
            {door.rule.references.map((r, i) =>
              r.url ? (
                <li key={r.id} className="space-y-1">
                  <ImageMarkup src={r.url} alt={`Door reference ${i + 1}`} shapes={[boxShape(r.box)]} readOnly className="rounded-lg" />
                  <span className="block text-center text-xs font-semibold">{r.status}</span>
                </li>
              ) : null,
            )}
          </ul>
        )}
      </section>
    </section>
  );
}

function StillCard({
  still,
  picked,
  zones,
  onView,
}: {
  still: TracedStill;
  picked: boolean;
  zones: ReturnType<typeof boxShape>[];
  onView: (v: Viewing) => void;
}) {
  const title = `Still ${still.n}`;
  return (
    <li aria-label={title} className={`${CARD} overflow-hidden ${still.open ? "ring-2 ring-emerald-400 dark:ring-emerald-600" : ""}`}>
      {still.url ? (
        <button type="button" aria-label={`View ${title}`} onClick={() => onView({ src: still.url!, title })} className="block w-full">
          <ImageMarkup src={still.url} alt={title} shapes={zones} readOnly />
        </button>
      ) : (
        <div className="grid aspect-video place-items-center bg-slate-100 px-2 text-center text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          {`Not downloaded (${still.missing_status ?? "error"})`}
        </div>
      )}
      <div className="space-y-1 p-2 text-xs">
        <div className="flex items-center justify-between gap-1">
          <span className="font-semibold">{title}</span>
          {still.open !== null && (
            <span className={still.open ? "font-semibold text-emerald-700 dark:text-emerald-300" : "text-slate-500 dark:text-slate-400"}>
              {still.open ? "Open" : "Closed"}
            </span>
          )}
        </div>
        {still.zones.map((z) => (
          <div key={z.zone} className={`tabular-nums ${z.zone === still.best_zone ? "font-semibold" : ""}`}>
            {`Zone ${z.zone}: ${score(z.value)} / ${z.threshold}`}
          </div>
        ))}
        {picked && <div className="font-semibold text-brand-700 dark:text-brand-300">Sent to analysis</div>}
      </div>
    </li>
  );
}

function blockLabel(block: RequestBlock): string {
  if (block.type === "image") return `${block.role === "reference" ? "Reference" : "Still"} ${block.n}`;
  return block.type === "cache_point" ? "cache point" : "text";
}

function NovaSection({ call, index, onView }: { call: NovaCall; index: number; onView: (v: Viewing) => void }) {
  const name = `Nova call ${index}`;
  const figures: [string, string][] = [
    ["Input tokens", whole(call.input_tokens)],
    ["Output tokens", whole(call.output_tokens)],
    ["Cache read", whole(call.cache_read_tokens)],
    ["Cache write", whole(call.cache_write_tokens)],
    ["Cost", `$${call.usd}`],
    ["Bedrock latency", call.latency_ms === null ? "—" : seconds(call.latency_ms, 2)],
    ["Wall time", seconds(call.wall_ms, 2)],
  ];
  return (
    <section aria-label={name} className="space-y-3">
      <h2 className={`${HEADING} flex items-center gap-2`}>
        {name}
        {call.outcome === "invalid" && (
          <span className="rounded-full bg-warm-200/80 px-2 py-0.5 normal-case tracking-normal text-warm-900 dark:bg-warm-900 dark:text-warm-100">
            Invalid answer
          </span>
        )}
        {call.outcome === "error" && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 normal-case tracking-normal text-red-800 dark:bg-red-950 dark:text-red-200">
            Failed
          </span>
        )}
      </h2>
      <div className={`${CARD} space-y-2 p-3`}>
        <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400">Request · {call.model_id}</h3>
        <ol className="flex flex-wrap items-start gap-2 text-sm">
          {call.request.content.map((block, i) => (
            <li key={i} data-testid="request-block" data-label={blockLabel(block)} className={block.type === "text" ? "basis-full" : ""}>
              {block.type === "text" && <p className="whitespace-pre-wrap break-words">{block.text}</p>}
              {block.type === "cache_point" && (
                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  cache point
                </span>
              )}
              {block.type === "image" && block.url && (
                <button
                  type="button"
                  aria-label={blockLabel(block)}
                  onClick={() => onView({ src: block.url!, title: blockLabel(block) })}
                  className="block w-24 overflow-hidden rounded-lg ring-1 ring-slate-200 dark:ring-slate-700"
                >
                  <img src={block.url} alt={blockLabel(block)} className="aspect-video w-full object-cover" />
                </button>
              )}
            </li>
          ))}
        </ol>
      </div>
      <div className={`${CARD} space-y-2 p-3`}>
        <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400">Response</h3>
        {call.outcome === "error" ? (
          <p className="text-sm font-semibold text-red-700 dark:text-red-300">{call.error_code}</p>
        ) : (
          <>
            {call.response?.stopReason && <p className="text-sm">{`Stop reason: ${call.response.stopReason}`}</p>}
            <pre className="max-h-72 overflow-auto rounded-lg bg-slate-100 p-2 text-xs dark:bg-slate-950">
              {JSON.stringify(call.response?.output ?? null, null, 2)}
              {"\n"}
              {JSON.stringify({ stopReason: call.response?.stopReason }, null, 2)}
            </pre>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm sm:grid-cols-4">
              {figures.map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
                  <dd className="font-semibold tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </div>
    </section>
  );
}
