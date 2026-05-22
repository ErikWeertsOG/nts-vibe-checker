import { useEffect, useMemo, useState } from "react";
import type { Act, Category, Festival, FestivalIndexEntry, Payload } from "./types";
import InstallModal from "./InstallModal";

type Tab = "vibe" | "all";

const DEFAULT_FESTIVAL: Festival = {
  id: "lowlands",
  name: "Lowlands 2026",
  url: "https://lowlands.nl/acts/",
};

const FALLBACK_INDEX: FestivalIndexEntry[] = [
  { id: "lowlands", name: "Lowlands 2026", file: "/acts.json", total: 0, generated_at: "" },
];

const THEME_BY_ID: Record<string, string> = {
  lowlands: "lowlands",
  hiddengarden: "hiddengarden",
  "demo-festival": "demo-festival",
};
const themeFor = (id: string) => THEME_BY_ID[id] ?? "default";

const TAGLINE_BY_ID: Record<string, string> = {
  lowlands: "A CAMPINGFLIGHT TO LOWLANDS PARADISE",
};
const taglineFor = (f: Festival) => TAGLINE_BY_ID[f.id] ?? `${f.name} × NTS`;
const introFor = (f: Festival) =>
  `Welke ${f.name}-acts dragen het hoogste NTS-gehalte? Score combineert harde NTS-aanwezigheid (eigen show, mixtape-credit) met aesthetic fit — Claude beoordeelt op basis van de bio of NTS dit zou draaien.`;

const actGenres = (a: Act): string[] =>
  a.genres && a.genres.length ? a.genres : a.lowlands_genres ?? [];

const categoryStyle: Record<Category, { bg: string; label: string }> = {
  RESIDENT:       { bg: "bg-ll-red text-ll-cream",        label: "NTS RESIDENT" },
  "NTS-PRESENCE": { bg: "bg-ll-blue text-ll-cream",       label: "NTS PRESENCE" },
  "NTS-VIBE":     { bg: "bg-ll-cyan text-ll-indigo",      label: "NTS VIBE" },
  ADJACENT:       { bg: "bg-ll-cream/30 text-ll-cream",   label: "ADJACENT" },
  OFF:            { bg: "bg-ll-indigo text-ll-cream/40",  label: "OFF SPECTRUM" },
};

function ScoreBadge({ score, category }: { score: number; category: Category }) {
  const { bg, label } = categoryStyle[category];
  return (
    <div className={`${bg} flex flex-col items-center justify-center w-[72px] h-[72px] shrink-0`}>
      <span className="font-display text-[34px] leading-none">{score}</span>
      <span className="ll-tag mt-1 text-[9px] text-center px-1">{label}</span>
    </div>
  );
}

function MiniBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 bg-ll-indigo h-1.5 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="font-display text-sm w-8 text-right">{value}</span>
    </div>
  );
}

function ActCard({
  act, expanded, onToggle, sourceLabel,
}: { act: Act; expanded: boolean; onToggle: () => void; sourceLabel: string }) {
  const genres = actGenres(act);
  return (
    <li className="border-b border-ll-indigo">
      <button onClick={onToggle} className="w-full text-left p-4 hover:bg-ll-indigo/40 transition-colors flex items-start gap-4">
        <ScoreBadge score={act.score} category={act.category} />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="font-display text-2xl text-ll-cream leading-tight">{act.name}</h2>
            {genres.length > 0 && (
              <span className="ll-tag text-ll-cyan/70">{genres.join(" · ")}</span>
            )}
          </div>
          {act.blurb && (
            <p className="text-sm text-ll-cream/80 mt-1.5 leading-relaxed font-body">{act.blurb}</p>
          )}
        </div>
        <span className="font-display text-2xl text-ll-cream/40 shrink-0 leading-none mt-1">{expanded ? "−" : "+"}</span>
      </button>
      {expanded && (
        <div className="px-4 pb-5 pl-[88px] text-sm space-y-4">
          <div className="space-y-2">
            <div className="ll-tag text-ll-cream/50">SCORES</div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-3">
                <span className="ll-tag text-ll-cream/70 w-20">PRESENCE</span>
                <div className="flex-1"><MiniBar value={act.presence_score} color="bg-ll-red" /></div>
              </div>
              <div className="flex items-center gap-3">
                <span className="ll-tag text-ll-cream/70 w-20">VIBE</span>
                <div className="flex-1"><MiniBar value={act.vibe_score} color="bg-ll-cyan" /></div>
              </div>
            </div>
          </div>

          {act.vibe_reason && (
            <div>
              <div className="ll-tag text-ll-cream/50 mb-1 flex items-center gap-2">
                <span>VIBE-OORDEEL</span>
                {act.overridden && (
                  <span className="bg-ll-red text-ll-cream px-1.5 py-0.5 text-[9px]">HANDMATIG</span>
                )}
              </div>
              <div className="text-ll-cream/90 font-body">{act.vibe_reason}</div>
            </div>
          )}

          {act.reasons.length > 0 && act.presence_score > 0 && (
            <div>
              <div className="ll-tag text-ll-cream/50 mb-1">NTS-SPOREN</div>
              <div className="text-ll-cream/90 font-body">{act.reasons.join(" · ")}</div>
            </div>
          )}

          {act.nts_genres.length > 0 && (
            <div>
              <div className="ll-tag text-ll-cream/50 mb-1">NTS-GENRES</div>
              <div className="text-ll-cream/90 font-body">{act.nts_genres.join(" · ")}</div>
            </div>
          )}

          {act.nts_links.length > 0 && (
            <div className="space-y-1">
              {act.nts_links.map((l) => (
                <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="block text-ll-cyan underline underline-offset-2 hover:text-white font-body text-sm">
                  → {l.label}
                </a>
              ))}
            </div>
          )}

          <div className="flex gap-2 pt-2 flex-wrap">
            <a href={act.url} target="_blank" rel="noopener noreferrer" className="ll-btn bg-ll-indigo text-ll-cyan hover:bg-ll-cyan hover:text-ll-indigo text-xs">
              {sourceLabel} →
            </a>
            {act.soundcloud && (
              <a href={act.soundcloud} target="_blank" rel="noopener noreferrer" className="ll-btn bg-ll-indigo text-ll-cyan hover:bg-ll-cyan hover:text-ll-indigo text-xs">
                SOUNDCLOUD →
              </a>
            )}
            {act.spotify && (
              <a href={act.spotify} target="_blank" rel="noopener noreferrer" className="ll-btn bg-ll-indigo text-ll-cyan hover:bg-ll-cyan hover:text-ll-indigo text-xs">
                SPOTIFY →
              </a>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export default function App() {
  const [index, setIndex] = useState<FestivalIndexEntry[]>(FALLBACK_INDEX);
  const [selectedId, setSelectedId] = useState<string>(() => {
    const p = new URLSearchParams(window.location.search).get("f");
    return p || "";
  });
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string>("");
  const [tab, setTab] = useState<Tab>("vibe");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [showInstall, setShowInstall] = useState(false);

  // Load the festival index, then settle on a selected festival.
  useEffect(() => {
    fetch("/festivals/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((idx: { festivals: FestivalIndexEntry[] }) => {
        const list = idx.festivals?.length ? idx.festivals : FALLBACK_INDEX;
        setIndex(list);
        setSelectedId((cur) => (cur && list.some((f) => f.id === cur) ? cur : list[0].id));
      })
      .catch(() => {
        setIndex(FALLBACK_INDEX);
        setSelectedId((cur) => cur || "lowlands");
      });
  }, []);

  // Load the selected festival's payload.
  useEffect(() => {
    if (!selectedId) return;
    const entry = index.find((f) => f.id === selectedId);
    const file = entry?.file ?? "/acts.json";
    setData(null);
    setErr("");
    setOpen({});
    fetch(file)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [selectedId, index]);

  const festival: Festival = useMemo(() => {
    if (data?.festival) return data.festival;
    const entry = index.find((f) => f.id === selectedId);
    if (entry) return { id: entry.id, name: entry.name, url: DEFAULT_FESTIVAL.url };
    return DEFAULT_FESTIVAL;
  }, [data, index, selectedId]);

  // Apply per-festival theme + document title.
  useEffect(() => {
    document.documentElement.dataset.theme = themeFor(festival.id);
    document.title = `NTS Vibe Checker — ${festival.name}`;
  }, [festival]);

  const selectFestival = (id: string) => {
    setSelectedId(id);
    const url = new URL(window.location.href);
    if (id === index[0]?.id) url.searchParams.delete("f");
    else url.searchParams.set("f", id);
    window.history.replaceState({}, "", url);
  };

  const filtered = useMemo(() => {
    if (!data) return [];
    let acts = data.acts;
    if (tab === "vibe") acts = acts.filter((a) => a.score >= 40);
    if (q) {
      const n = q.toLowerCase();
      acts = acts.filter((a) =>
        a.name.toLowerCase().includes(n) ||
        a.bio.toLowerCase().includes(n) ||
        actGenres(a).some((g) => g.toLowerCase().includes(n))
      );
    }
    return acts;
  }, [data, tab, q]);

  if (err) return <div className="min-h-screen bg-ll-indigo-deep p-8 text-ll-red">Error: {err}</div>;
  if (!data) return <div className="min-h-screen bg-ll-indigo-deep p-8 text-ll-cream/60">Loading…</div>;

  const isLowlands = festival.id === "lowlands";
  const sourceLabel = isLowlands ? "LOWLANDS" : festival.name.toUpperCase();

  return (
    <div className="min-h-screen bg-ll-indigo-deep">
      <div className="max-w-3xl mx-auto px-4 pb-24">
        <header className="pt-12 pb-8 border-b-4 border-ll-red relative">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="ll-tag text-ll-cyan mb-2">{taglineFor(festival)}</div>
            {index.length > 1 && (
              <select
                value={festival.id}
                onChange={(e) => selectFestival(e.target.value)}
                className="ll-btn bg-ll-indigo text-ll-cyan border-2 border-ll-indigo focus:border-ll-cyan outline-none text-sm cursor-pointer"
                aria-label="Kies festival"
              >
                {index.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            )}
          </div>
          <h1 className="font-display text-ll-cream text-[64px] sm:text-[88px] leading-[0.85] tracking-tight">
            NTS<br/>VIBE<br/>CHECKER
          </h1>
          <p className="text-ll-cream/80 mt-6 max-w-xl font-body leading-relaxed">
            {introFor(festival)}
          </p>
          <div className="ll-tag text-ll-cream/50 mt-4">
            {data.stats.with_own_show} EIGEN NTS-SHOWS · {data.stats.with_presence} MET NTS-SPOREN · {data.stats.with_vibe_70_plus} MET STERKE VIBE
          </div>
          {isLowlands && (
            <button
              onClick={() => setShowInstall(true)}
              className="mt-5 ll-btn bg-ll-red text-ll-cream hover:bg-ll-cyan hover:text-ll-indigo text-sm"
            >
              ACTIVEER OP LOWLANDS.NL →
            </button>
          )}
        </header>
        {showInstall && <InstallModal onClose={() => setShowInstall(false)} />}

        <div className="sticky top-0 bg-ll-indigo-deep/95 backdrop-blur py-3 z-10 border-b border-ll-indigo flex gap-2 items-center">
          <div className="flex gap-0">
            {(["vibe", "all"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`ll-btn text-sm ${
                  tab === t
                    ? "bg-ll-cyan text-ll-indigo"
                    : "bg-ll-indigo text-ll-cream/80 hover:text-ll-cream"
                }`}
              >
                {t === "vibe" ? "NTS-VIBE (40+)" : `ALLE ${data.stats.total}`}
              </button>
            ))}
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="zoek act / genre..."
            className="ml-auto bg-ll-indigo text-ll-cream px-3 py-2 text-sm border-2 border-ll-indigo focus:border-ll-cyan outline-none w-44 font-body placeholder:text-ll-cream/40"
          />
        </div>

        <ul>
          {filtered.map((a) => (
            <ActCard key={a.slug} act={a} expanded={!!open[a.slug]} sourceLabel={sourceLabel} onToggle={() => setOpen((o) => ({ ...o, [a.slug]: !o[a.slug] }))} />
          ))}
        </ul>

        {filtered.length === 0 && (
          <p className="text-ll-cream/40 p-8 text-center font-body">Geen acts gevonden.</p>
        )}

        <footer className="mt-12 pt-6 border-t border-ll-indigo flex justify-between items-baseline gap-4 flex-wrap">
          <div className="ll-tag text-ll-cream/40">
            {isLowlands ? "GEBOUWD VOOR LL26 · DATA NTS.LIVE + LOWLANDS.NL · VIBE VIA CLAUDE" : "DATA NTS.LIVE · VIBE VIA CLAUDE"}
          </div>
          <div className="ll-tag text-ll-cream/40">{data.generated_at.slice(0, 10)}</div>
        </footer>
      </div>
    </div>
  );
}
