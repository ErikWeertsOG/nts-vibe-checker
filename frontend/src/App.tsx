import { useEffect, useMemo, useState } from "react";
import type { Act, Payload } from "./types";

type Tab = "all" | "vibe" | "now";

const scoreColor = (s: number) => {
  if (s >= 90) return "bg-yellow-400 text-black";
  if (s >= 75) return "bg-orange-400 text-black";
  if (s >= 50) return "bg-pink-400 text-black";
  if (s >= 1) return "bg-zinc-600 text-white";
  return "bg-zinc-900 text-zinc-500";
};

const scoreLabel = (s: number) => {
  if (s >= 90) return "NTS BAAS";
  if (s >= 75) return "NTS";
  if (s >= 50) return "NTS-ADJACENT";
  if (s >= 1) return "WHIFF";
  return "—";
};

function ScoreBadge({ score }: { score: number }) {
  return (
    <div className={`nts-mono font-bold ${scoreColor(score)} flex flex-col items-center justify-center w-14 h-14 shrink-0`}>
      <span className="text-xl leading-none">{score}</span>
      <span className="text-[8px] opacity-80 mt-1">{scoreLabel(score)}</span>
    </div>
  );
}

function ActCard({ act, expanded, onToggle }: { act: Act; expanded: boolean; onToggle: () => void }) {
  return (
    <li className="border-b border-zinc-800">
      <button onClick={onToggle} className="w-full text-left p-4 hover:bg-zinc-950 transition-colors flex items-start gap-4">
        <ScoreBadge score={act.score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-lg font-semibold">{act.name}</h2>
            {act.own_show && (
              <span className="text-[10px] nts-mono text-yellow-400">NTS RESIDENT</span>
            )}
          </div>
          {act.blurb ? (
            <p className="text-sm text-zinc-300 mt-1 leading-relaxed">{act.blurb}</p>
          ) : (
            <p className="text-sm text-zinc-500 mt-1 italic">{act.reasons[0]}</p>
          )}
        </div>
        <span className="text-zinc-600 nts-mono text-xs mt-1 shrink-0">{expanded ? "−" : "+"}</span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pl-20 text-sm space-y-3">
          {act.genres.length > 0 && (
            <div>
              <span className="text-zinc-500 nts-mono text-xs">GENRES </span>
              <span className="text-zinc-300">{act.genres.join(" · ")}</span>
            </div>
          )}
          {act.moods.length > 0 && (
            <div>
              <span className="text-zinc-500 nts-mono text-xs">MOODS </span>
              <span className="text-zinc-300">{act.moods.join(" · ")}</span>
            </div>
          )}
          <div>
            <span className="text-zinc-500 nts-mono text-xs">SIGNAL </span>
            <span className="text-zinc-300">{act.reasons.join(" · ")}</span>
          </div>
          {act.nts_links.length > 0 && (
            <div className="space-y-1">
              {act.nts_links.map((l) => (
                <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="block text-yellow-400 underline hover:text-yellow-300">
                  → {l.label}
                </a>
              ))}
            </div>
          )}
          <a href={act.url} target="_blank" rel="noopener noreferrer" className="block text-zinc-500 hover:text-zinc-300 text-xs nts-mono">
            LOWLANDS.NL/{act.slug.toUpperCase()}
          </a>
        </div>
      )}
    </li>
  );
}

export default function App() {
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string>("");
  const [tab, setTab] = useState<Tab>("vibe");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch("/acts.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    let acts = data.acts;
    if (tab === "vibe") acts = acts.filter((a) => a.score > 0);
    if (q) {
      const n = q.toLowerCase();
      acts = acts.filter((a) => a.name.toLowerCase().includes(n));
    }
    return acts;
  }, [data, tab, q]);

  if (err) return <div className="p-8 text-red-400">Error: {err}</div>;
  if (!data) return <div className="p-8 text-zinc-500">Loading…</div>;

  return (
    <div className="max-w-3xl mx-auto px-4 pb-24">
      <header className="pt-10 pb-6 border-b border-zinc-800">
        <h1 className="text-3xl font-bold nts-mono">NTS VIBE CHECKER</h1>
        <p className="text-zinc-400 mt-2">
          Welke Lowlands 2026-acts halen het hoogste NTS-gehalte? Score 0–100 op basis van eigen NTS-show, mixtape-credits en guest-vermeldingen.
        </p>
        <p className="text-zinc-600 text-xs nts-mono mt-2">
          {data.stats.with_any_signal} van {data.stats.total} acts hebben NTS-sporen. {data.stats.with_own_show} hebben een eigen show.
        </p>
      </header>

      <div className="sticky top-0 bg-black/95 backdrop-blur py-3 z-10 border-b border-zinc-800 flex gap-2 items-center">
        <div className="flex nts-mono text-xs">
          {(["vibe", "all"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 ${tab === t ? "bg-white text-black" : "text-zinc-400 hover:text-white"}`}
            >
              {t === "vibe" ? "ALLEEN NTS-VIBE" : "ALLE ACTS"}
            </button>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="zoek act..."
          className="ml-auto bg-zinc-900 text-white px-3 py-2 text-sm border border-zinc-800 focus:border-yellow-400 outline-none w-40"
        />
      </div>

      <ul>
        {filtered.map((a) => (
          <ActCard key={a.slug} act={a} expanded={!!open[a.slug]} onToggle={() => setOpen((o) => ({ ...o, [a.slug]: !o[a.slug] }))} />
        ))}
      </ul>

      {filtered.length === 0 && (
        <p className="text-zinc-500 p-8 text-center">Geen acts gevonden.</p>
      )}

      <footer className="mt-12 pt-6 border-t border-zinc-800 text-xs text-zinc-600 nts-mono">
        gebouwd voor LL26 · data via nts.live + lowlands.nl · gegenereerd {data.generated_at.slice(0, 10)}
      </footer>
    </div>
  );
}
