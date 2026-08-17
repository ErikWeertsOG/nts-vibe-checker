import { useEffect, useMemo, useState } from "react";
import type { Act, Category, RawSlot } from "./types";

const STAGES = ["ALPHA","BRAVO","HEINEKEN","LIMA","INDIA","X-RAY","HACIENDA","JULIET","ADONIS"];
const DAYS = [
  { iso: "2026-08-21", label: "VR 21", full: "VRIJDAG 21 AUGUSTUS" },
  { iso: "2026-08-22", label: "ZA 22", full: "ZATERDAG 22 AUGUSTUS" },
  { iso: "2026-08-23", label: "ZO 23", full: "ZONDAG 23 AUGUSTUS" },
];
const START_HOUR = 9.5;             // 09:30
const DAY_MINUTES = 19.5 * 60;      // 09:30 → 05:00 next day = 1170 min
const PX_PER_MIN = 2.4;             // → grid width ~2800px (scrolls on mobile)

const CAT_CLS: Record<Category, string> = {
  RESIDENT:       "bg-ll-red text-ll-cream",
  "NTS-PRESENCE": "bg-ll-blue text-ll-cream",
  "NTS-VIBE":     "bg-ll-cyan text-ll-indigo",
  ADJACENT:       "bg-ll-cream/25 text-ll-cream",
  OFF:            "bg-ll-indigo text-ll-cream/40",
};
const CAT_ORDER: Record<Category, number> = {
  RESIDENT: 5, "NTS-PRESENCE": 4, "NTS-VIBE": 3, ADJACENT: 2, OFF: 1,
};

function toMin(time: string): number {
  const [h, m] = time.split(":").map(Number);
  let hours = h + m / 60;
  if (hours < START_HOUR) hours += 24;   // wrap past midnight → same-day timeline
  return (hours - START_HOUR) * 60;
}

function nowInFestival(): { day: string; minute: number } | null {
  const now = new Date();
  const iso = now.toISOString().slice(0, 10);
  const dayIdx = DAYS.findIndex(d => d.iso === iso);
  if (dayIdx === -1) {
    // Also consider previous festival day between 00:00 and 05:00 (still "yesterday's night")
    const prev = new Date(now.getTime() - 6 * 3600 * 1000).toISOString().slice(0, 10);
    const pIdx = DAYS.findIndex(d => d.iso === prev);
    if (pIdx === -1) return null;
    const min = toMin(`${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`);
    return { day: prev, minute: min };
  }
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  return { day: iso, minute: toMin(`${hh}:${mm}`) };
}

type Enriched = RawSlot & {
  act?: Act;
  category: Category;
  score: number;
  startMin: number;
  endMin: number;
};

function humanTimeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (isNaN(then)) return "";
  const diffSec = (Date.now() - then) / 1000;
  if (diffSec < 60) return "zojuist bijgewerkt";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min geleden bijgewerkt`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}u geleden bijgewerkt`;
  return `${Math.floor(diffSec / 86400)}d geleden bijgewerkt`;
}

export default function Timetable({ acts, rawSlots, updatedAt }: {
  acts: Act[]; rawSlots: RawSlot[]; updatedAt?: string;
}) {
  const nowFest = useMemo(nowInFestival, []);
  const [day, setDay] = useState<string>(nowFest?.day ?? DAYS[0].iso);
  const [minCat, setMinCat] = useState<number>(0);           // 0=all, 2=adjacent+, 3=vibe+, 4=presence+
  const [nowMode, setNowMode] = useState<boolean>(!!nowFest);
  const [selected, setSelected] = useState<Enriched | null>(null);

  const setKeyToAct = useMemo(() => {
    const m = new Map<string, Act>();
    for (const a of acts) {
      for (const s of a.sets ?? []) {
        m.set(`${s.day}|${s.stage}|${s.start_time}|${s.raw_name ?? ""}`, a);
      }
    }
    return m;
  }, [acts]);

  // Enrich raw slots with act (if matched) and computed positions.
  const enriched: Enriched[] = useMemo(() => {
    // group per stage/day to compute end times = next-slot start on same stage.
    const buckets: Record<string, RawSlot[]> = {};
    for (const s of rawSlots) {
      const k = `${s.day}|${s.stage}`;
      (buckets[k] ??= []).push(s);
    }
    const out: Enriched[] = [];
    for (const [k, list] of Object.entries(buckets)) {
      list.sort((a, b) => toMin(a.start_time) - toMin(b.start_time));
      for (let i = 0; i < list.length; i++) {
        const s = list[i];
        const startMin = toMin(s.start_time);
        const nextMin = i + 1 < list.length ? toMin(list[i + 1].start_time) : DAY_MINUTES;
        const endMin = Math.min(nextMin, DAY_MINUTES);
        const act = setKeyToAct.get(`${s.day}|${s.stage}|${s.start_time}|${s.name}`);
        const category: Category = act ? act.category : "OFF";
        out.push({
          ...s, act, category,
          score: act?.score ?? 0,
          startMin, endMin,
        });
      }
    }
    return out;
  }, [rawSlots, setKeyToAct]);

  const daySlots = useMemo(
    () => enriched.filter(s => s.day === day)
                  .filter(s => minCat === 0 || CAT_ORDER[s.category] >= minCat),
    [enriched, day, minCat]
  );

  const stagesWithSlots = STAGES.filter(stg => daySlots.some(s => s.stage === stg));

  // "NU" line position (if today is a festival day and we're viewing that day)
  const nowLineMin = nowFest && nowFest.day === day && nowMode ? nowFest.minute : null;

  // Auto-scroll to now when NU-mode active
  useEffect(() => {
    if (nowLineMin != null) {
      const el = document.getElementById("tt-scroll");
      if (el) {
        const target = Math.max(0, nowLineMin * PX_PER_MIN - el.clientWidth / 3);
        el.scrollLeft = target;
      }
    }
  }, [nowLineMin]);

  const hours = Array.from({ length: 20 }, (_, i) => 9 + i);  // 09..28
  const totalW = DAY_MINUTES * PX_PER_MIN;

  return (
    <div>
      {/* Day tabs + filter */}
      <div className="sticky top-0 bg-ll-indigo-deep/95 backdrop-blur z-20 border-b border-ll-indigo py-3 flex gap-2 items-center flex-wrap">
        <div className="flex gap-0">
          {DAYS.map(d => (
            <button key={d.iso}
              onClick={() => setDay(d.iso)}
              className={`ll-btn text-sm ${day === d.iso ? "bg-ll-cyan text-ll-indigo" : "bg-ll-indigo text-ll-cream/80 hover:text-ll-cream"}`}>
              {d.label}
            </button>
          ))}
        </div>
        {nowFest && (
          <button onClick={() => setNowMode(v => !v)}
            className={`ll-btn text-sm ${nowMode ? "bg-ll-red text-ll-cream" : "bg-ll-indigo text-ll-cream/60 hover:text-ll-cream"}`}>
            NU
          </button>
        )}
        <div className="flex gap-0 ml-auto">
          {[
            { v: 0, label: "ALLES" },
            { v: 2, label: "40+" },
            { v: 3, label: "VIBE 70+" },
            { v: 4, label: "PRESENCE" },
          ].map(o => (
            <button key={o.v} onClick={() => setMinCat(o.v)}
              className={`ll-btn text-xs ${minCat === o.v ? "bg-ll-cyan text-ll-indigo" : "bg-ll-indigo text-ll-cream/70 hover:text-ll-cream"}`}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 mb-2 flex justify-between items-baseline gap-4">
        <span className="ll-tag text-ll-cream/50">{DAYS.find(d => d.iso === day)?.full}</span>
        {updatedAt && (
          <span className="ll-tag text-ll-cream/40 text-[10px]">{humanTimeAgo(updatedAt)}</span>
        )}
      </div>

      {/* Timeline */}
      <div id="tt-scroll" className="overflow-x-auto border border-ll-indigo bg-ll-indigo/30">
        <div style={{ width: totalW + 90, position: "relative" }}>
          {/* time header */}
          <div className="flex sticky top-0 z-10" style={{ paddingLeft: 90 }}>
            {hours.map(h => {
              const label = h >= 24 ? String(h - 24).padStart(2, "0") : String(h).padStart(2, "0");
              const min = (h - START_HOUR) * 60;
              return (
                <div key={h}
                  className="ll-tag text-ll-cream/60 py-1 border-l border-ll-indigo bg-ll-indigo-deep"
                  style={{ position: "absolute", left: 90 + min * PX_PER_MIN, width: 60 * PX_PER_MIN }}>
                  {label}:00
                </div>
              );
            })}
          </div>
          <div style={{ height: 22 }} />

          {/* Stage rows */}
          {stagesWithSlots.map(stg => (
            <div key={stg} className="relative border-t border-ll-indigo"
                 style={{ height: 56 }}>
              <div className="absolute left-0 top-0 h-full flex items-center px-2 bg-ll-indigo-deep z-10 border-r border-ll-indigo"
                   style={{ width: 90 }}>
                <span className="ll-tag text-ll-cream">{stg}</span>
              </div>
              <div className="absolute inset-y-0" style={{ left: 90, right: 0 }}>
                {/* Hour grid lines */}
                {hours.map(h => {
                  const min = (h - START_HOUR) * 60;
                  return (
                    <div key={h} className="absolute inset-y-0 border-l border-ll-indigo/60"
                         style={{ left: min * PX_PER_MIN }} />
                  );
                })}
                {/* Slots */}
                {daySlots.filter(s => s.stage === stg).map(s => {
                  const left = s.startMin * PX_PER_MIN;
                  const width = Math.max((s.endMin - s.startMin) * PX_PER_MIN - 2, 28);
                  const isNow = nowLineMin != null && s.startMin <= nowLineMin && nowLineMin < s.endMin;
                  return (
                    <button
                      key={`${s.day}${s.stage}${s.start_time}`}
                      onClick={() => setSelected(s)}
                      title={`${s.act?.name ?? s.name} · ${s.start_time}`}
                      className={`absolute top-1 bottom-1 px-2 py-1 text-left overflow-hidden flex flex-col justify-between ${CAT_CLS[s.category]} ${isNow ? "ring-2 ring-ll-red" : ""} hover:z-10 hover:scale-[1.02] transition-transform`}
                      style={{ left, width }}>
                      <div className="ll-tag text-[10px] opacity-70 flex items-center gap-1 shrink-0">
                        <span>{s.start_time}</span>
                        {s.act && <span className="font-display">· {s.score}</span>}
                      </div>
                      <div className="font-display text-[13px] leading-tight truncate">
                        {s.act?.name ?? s.name}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {/* NOW line */}
          {nowLineMin != null && (
            <div className="absolute top-0 bottom-0 border-l-2 border-ll-red z-20 pointer-events-none"
                 style={{ left: 90 + nowLineMin * PX_PER_MIN }}>
              <div className="ll-tag bg-ll-red text-ll-cream px-1 py-0.5 -translate-x-1/2 inline-block text-[10px]">
                NU
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-2 items-center text-xs">
        <span className="ll-tag text-ll-cream/50">CATEGORIE:</span>
        {(["RESIDENT","NTS-PRESENCE","NTS-VIBE","ADJACENT","OFF"] as Category[]).map(c => (
          <span key={c} className={`ll-tag px-2 py-1 ${CAT_CLS[c]}`}>{c}</span>
        ))}
      </div>

      {selected && <SlotDetail slot={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function SlotDetail({ slot, onClose }: { slot: Enriched; onClose: () => void }) {
  const a = slot.act;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start sm:items-center justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
           className={`max-w-lg w-full p-5 border-2 border-ll-red bg-ll-indigo-deep`}>
        <div className="flex justify-between items-start gap-4 mb-2">
          <div>
            <div className="ll-tag text-ll-cyan mb-1">{slot.stage} · {slot.day.slice(-5)} · {slot.start_time}</div>
            <h2 className="font-display text-3xl text-ll-cream leading-tight">{a?.name ?? slot.name}</h2>
          </div>
          <button onClick={onClose} className="font-display text-3xl text-ll-cream/60 hover:text-ll-cream leading-none">×</button>
        </div>
        <div className={`inline-block ll-tag px-2 py-1 mb-3 ${CAT_CLS[slot.category]}`}>
          {slot.category} {a ? `· ${a.score}` : ""}
        </div>
        {a?.blurb && <p className="text-sm text-ll-cream/90 font-body mb-3 leading-relaxed">{a.blurb}</p>}
        {a?.vibe_reason && (
          <div className="mb-3">
            <div className="ll-tag text-ll-cream/50 mb-1">VIBE-OORDEEL</div>
            <div className="text-sm text-ll-cream/90 font-body">{a.vibe_reason}</div>
          </div>
        )}
        {!a && (
          <p className="text-sm text-ll-cream/70 font-body">Deze act staat niet in de line-up-API — geen NTS-score beschikbaar.</p>
        )}
        <div className="flex gap-2 flex-wrap pt-2">
          {a?.url && <a href={a.url} target="_blank" rel="noopener noreferrer" className="ll-btn bg-ll-indigo text-ll-cyan hover:bg-ll-cyan hover:text-ll-indigo text-xs">LOWLANDS →</a>}
          {a?.soundcloud && <a href={a.soundcloud} target="_blank" rel="noopener noreferrer" className="ll-btn bg-ll-indigo text-ll-cyan hover:bg-ll-cyan hover:text-ll-indigo text-xs">SOUNDCLOUD →</a>}
          {a?.spotify && <a href={a.spotify} target="_blank" rel="noopener noreferrer" className="ll-btn bg-ll-indigo text-ll-cyan hover:bg-ll-cyan hover:text-ll-indigo text-xs">SPOTIFY →</a>}
        </div>
      </div>
    </div>
  );
}
