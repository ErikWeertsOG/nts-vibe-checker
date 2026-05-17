import { useEffect, useMemo, useState } from "react";
import type { Act, Category, Payload } from "./types";

type Tab = "vibe" | "all";

const categoryStyle: Record<Category, { bg: string; label: string }> = {
  RESIDENT: { bg: "bg-yellow-400 text-black", label: "NTS RESIDENT" },
  "NTS-PRESENCE": { bg: "bg-yellow-200 text-black", label: "NTS PRESENCE" },
  "NTS-VIBE": { bg: "bg-pink-400 text-black", label: "NTS VIBE" },
  ADJACENT: { bg: "bg-zinc-500 text-white", label: "ADJACENT" },
  OFF: { bg: "bg-zinc-900 text-zinc-600", label: "OFF SPECTRUM" },
};

function ScoreBadge({ score, category }: { score: number; category: Category }) {
  const { bg, label } = categoryStyle[category];
  return (
    <div className={`nts-mono font-bold ${bg} flex flex-col items-center justify-center w-16 h-16 shrink-0`}>
      <span className="text-2xl leading-none">{score}</span>
      <span className="text-[8px] opacity-80 mt-1 text-center px-1 leading-tight">{label}</span>
    </div>
  );
}

function MiniBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-zinc-900 h-1 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="nts-mono text-xs w-8 text-right">{value}</span>
    </div>
  );
}

function ActCard({ act, expanded, onToggle }: { act: Act; expanded: boolean; onToggle: () => void }) {
  return (
    <li className="border-b border-zinc-800">
      <button onClick={onToggle} className="w-full text-left p-4 hover:bg-zinc-950 transition-colors flex items-start gap-4">
        <ScoreBadge score={act.score} category={act.category} />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-lg font-semibold">{act.name}</h2>
            {act.lowlands_genres.length > 0 && (
              <span className="text-xs nts-mono text-zinc-500">{act.lowlands_genres.join(" · ").toUpperCase()}</span>
            )}
          </div>
          {act.blurb && (
            <p className="text-sm text-zinc-300 mt-1 leading-relaxed">{act.blurb}</p>
          )}
        </div>
        <span className="text-zinc-600 nts-mono text-xs mt-1 shrink-0">{expanded ? "−" : "+"}</span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pl-20 text-sm space-y-4">
          <div className="space-y-2">
            <div className="text-zinc-500 nts-mono text-xs">SCORES</div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 w-20 nts-mono">PRESENCE</span>
                <div className="flex-1"><MiniBar value={act.presence_score} color="bg-yellow-400" /></div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 w-20 nts-mono">VIBE</span>
                <div className="flex-1"><MiniBar value={act.vibe_score} color="bg-pink-400" /></div>
              </div>
            </div>
          </div>

          {act.vibe_reason && (
            <div>
              <span className="text-zinc-500 nts-mono text-xs">VIBE-OORDEEL </span>
              <span className="text-zinc-300">{act.vibe_reason}</span>
            </div>
          )}

          {act.reasons.length > 0 && act.presence_score > 0 && (
            <div>
              <span className="text-zinc-500 nts-mono text-xs">NTS-SPOREN </span>
              <span className="text-zinc-300">{act.reasons.join(" · ")}</span>
            </div>
          )}

          {act.nts_genres.length > 0 && (
            <div>
              <span className="text-zinc-500 nts-mono text-xs">NTS-GENRES </span>
              <span className="text-zinc-300">{act.nts_genres.join(" · ")}</span>
            </div>
          )}

          {act.nts_links.length > 0 && (
            <div className="space-y-1">
              {act.nts_links.map((l) => (
                <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="block text-yellow-400 underline hover:text-yellow-300">
                  → {l.label}
                </a>
              ))}
            </div>
          )}

          <div className="flex gap-3 nts-mono text-xs pt-2">
            <a href={act.url} target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-zinc-300">
              LOWLANDS →
            </a>
            {act.soundcloud && (
              <a href={act.soundcloud} target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-zinc-300">
                SOUNDCLOUD →
              </a>
            )}
            {act.spotify && (
              <a href={act.spotify} target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-zinc-300">
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
    if (tab === "vibe") acts = acts.filter((a) => a.score >= 40);
    if (q) {
      const n = q.toLowerCase();
      acts = acts.filter((a) =>
        a.name.toLowerCase().includes(n) ||
        a.bio.toLowerCase().includes(n) ||
        a.lowlands_genres.some((g) => g.toLowerCase().includes(n))
      );
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
          Welke Lowlands 2026-acts dragen het hoogste NTS-gehalte? Score combineert harde NTS-aanwezigheid (eigen show, mixtape-credit) met aesthetic fit (Claude beoordeelt op basis van de bio of NTS dit zou draaien).
        </p>
        <p className="text-zinc-600 text-xs nts-mono mt-2">
          {data.stats.with_own_show} eigen NTS-shows · {data.stats.with_presence} met NTS-sporen · {data.stats.with_vibe_70_plus} met sterke vibe (≥70)
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
              {t === "vibe" ? "NTS-VIBE (40+)" : "ALLE 126"}
            </button>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="zoek act / genre..."
          className="ml-auto bg-zinc-900 text-white px-3 py-2 text-sm border border-zinc-800 focus:border-yellow-400 outline-none w-44"
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
        gebouwd voor LL26 · data via nts.live + lowlands.nl · vibe via claude · gegenereerd {data.generated_at.slice(0, 10)}
      </footer>
    </div>
  );
}
