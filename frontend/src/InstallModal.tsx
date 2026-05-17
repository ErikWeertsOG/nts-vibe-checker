import { useEffect, useState } from "react";

const BOOKMARKLET = `javascript:(function(){var d=document,s=d.createElement('script');s.src='https://nts-vibe-checker.vercel.app/inject.js?t='+Date.now();d.body.appendChild(s);})();`;
const USERSCRIPT_URL = "https://nts-vibe-checker.vercel.app/ntsvc.user.js";

function detectPlatform(): "ios" | "android" | "desktop" {
  const ua = navigator.userAgent;
  if (/iPhone|iPad|iPod/.test(ua)) return "ios";
  if (/Android/.test(ua)) return "android";
  return "desktop";
}

export default function InstallModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"ios" | "android" | "desktop">("desktop");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setTab(detectPlatform());
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(BOOKMARKLET);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Kopieer deze bookmarklet:", BOOKMARKLET);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start sm:items-center justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div
        className="bg-ll-indigo-deep border border-ll-red max-w-2xl w-full p-6 my-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4 gap-4">
          <div>
            <div className="ll-tag text-ll-cyan mb-2">INSTALLEER OP LOWLANDS.NL</div>
            <h2 className="font-display text-4xl text-ll-cream leading-tight">NTS BADGES OVERAL</h2>
          </div>
          <button onClick={onClose} className="font-display text-3xl text-ll-cream/60 hover:text-ll-cream leading-none">×</button>
        </div>

        <p className="text-ll-cream/80 mb-6 font-body">
          Activeer de NTS Vibe Checker direct op <span className="text-ll-cyan">lowlands.nl</span> — score-badges naast elke act, een floating widget op detail-pagina's, en een "Waarom?"-paneel met de blurb en NTS-links.
        </p>

        <div className="flex gap-0 mb-6">
          {(["desktop", "ios", "android"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`ll-btn text-sm ${tab === t ? "bg-ll-cyan text-ll-indigo" : "bg-ll-indigo text-ll-cream/80"}`}
            >
              {t === "desktop" ? "DESKTOP" : t === "ios" ? "IPHONE" : "ANDROID"}
            </button>
          ))}
        </div>

        {tab === "desktop" && (
          <div className="space-y-4 text-ll-cream/90 font-body">
            <p>Maak één keer een bladwijzer aan. Daarna tik je 'm op elke Lowlands-pagina om de overlay te activeren.</p>
            <ol className="list-decimal pl-6 space-y-2 text-sm">
              <li>Zorg dat je bladwijzerbalk zichtbaar is (Chrome: <kbd className="bg-ll-indigo px-1.5 py-0.5 text-xs">⌘+Shift+B</kbd>)</li>
              <li>
                Sleep deze knop ernaartoe:{" "}
                <a
                  href={BOOKMARKLET}
                  className="inline-block bg-ll-red text-ll-cream ll-btn text-sm no-underline"
                  onClick={(e) => e.preventDefault()}
                  draggable="true"
                >
                  → NTS VIBE
                </a>
              </li>
              <li>Open <a href="https://lowlands.nl/acts/" className="text-ll-cyan underline" target="_blank" rel="noopener">lowlands.nl/acts</a>, tik de bladwijzer</li>
            </ol>
            <p className="text-xs text-ll-cream/50">Slepen werkt niet? Kopieer de bookmarklet hieronder en maak handmatig een bladwijzer met die URL.</p>
            <div className="bg-ll-indigo p-3 break-all text-xs font-mono text-ll-cyan/80 select-all">{BOOKMARKLET}</div>
            <button onClick={copy} className="ll-btn bg-ll-indigo text-ll-cream text-sm hover:bg-ll-cyan hover:text-ll-indigo">
              {copied ? "GEKOPIEERD ✓" : "KOPIEER BOOKMARKLET"}
            </button>
          </div>
        )}

        {tab === "ios" && (
          <div className="space-y-5 text-ll-cream/90 font-body">
            <section>
              <div className="ll-tag text-ll-red mb-2">AANBEVOLEN — AUTOMATISCH</div>
              <h3 className="font-display text-xl text-ll-cream mb-2">Via Userscripts (gratis app)</h3>
              <p className="text-sm mb-2">Werkt zonder iets te tikken — opent automatisch zodra je een Lowlands-pagina opent in Safari.</p>
              <ol className="list-decimal pl-6 space-y-2 text-sm">
                <li>Installeer <a href="https://apps.apple.com/app/userscripts/id1463298887" target="_blank" rel="noopener" className="text-ll-cyan underline">Userscripts</a> uit de App Store (gratis)</li>
                <li>Schakel 'm in via <em>Instellingen → Safari → Extensies</em></li>
                <li>Open Safari op deze pagina, tik dan op het Userscripts-icoontje in de adresbalk</li>
                <li>
                  Tik op <em>+</em> → <em>New Remote</em> en plak deze URL:
                  <div className="bg-ll-indigo p-2 break-all text-xs font-mono text-ll-cyan/80 select-all mt-1">{USERSCRIPT_URL}</div>
                </li>
                <li>Klaar — open <a href="https://lowlands.nl/acts/" target="_blank" rel="noopener" className="text-ll-cyan underline">lowlands.nl/acts</a></li>
              </ol>
            </section>

            <section className="border-t border-ll-indigo pt-4">
              <div className="ll-tag text-ll-cream/50 mb-2">ALTERNATIEF — HANDMATIG TIKKEN</div>
              <h3 className="font-display text-xl text-ll-cream mb-2">Bookmarklet</h3>
              <ol className="list-decimal pl-6 space-y-2 text-sm">
                <li>Tik de share-knop in Safari → "Voeg toe aan bladwijzers" (kies een willekeurige pagina)</li>
                <li>Open Bladwijzers, tap "Wijzig", open die nieuwe bladwijzer</li>
                <li>Vervang de URL door de tekst hieronder en sla op</li>
                <li>Open lowlands.nl, tik die bladwijzer aan</li>
              </ol>
              <div className="bg-ll-indigo p-2 break-all text-xs font-mono text-ll-cyan/80 select-all mt-2">{BOOKMARKLET}</div>
              <button onClick={copy} className="ll-btn bg-ll-indigo text-ll-cream text-sm hover:bg-ll-cyan hover:text-ll-indigo mt-2">
                {copied ? "GEKOPIEERD ✓" : "KOPIEER"}
              </button>
            </section>
          </div>
        )}

        {tab === "android" && (
          <div className="space-y-5 text-ll-cream/90 font-body">
            <section>
              <div className="ll-tag text-ll-red mb-2">AANBEVOLEN — IN CHROME</div>
              <h3 className="font-display text-xl text-ll-cream mb-2">Bookmarklet</h3>
              <ol className="list-decimal pl-6 space-y-2 text-sm">
                <li>Kopieer de tekst hieronder</li>
                <li>Open Chrome → een willekeurige pagina → maak een bladwijzer</li>
                <li>Wijzig die bladwijzer (drie-puntjes-menu → Bladwijzers → bewerk)</li>
                <li>Vervang de URL door de gekopieerde tekst en sla op</li>
                <li>Open lowlands.nl, tik dezelfde bladwijzer in Chrome → overlay verschijnt</li>
              </ol>
              <div className="bg-ll-indigo p-2 break-all text-xs font-mono text-ll-cyan/80 select-all mt-2">{BOOKMARKLET}</div>
              <button onClick={copy} className="ll-btn bg-ll-indigo text-ll-cream text-sm hover:bg-ll-cyan hover:text-ll-indigo mt-2">
                {copied ? "GEKOPIEERD ✓" : "KOPIEER BOOKMARKLET"}
              </button>
            </section>

            <section className="border-t border-ll-indigo pt-4">
              <div className="ll-tag text-ll-cream/50 mb-2">ALTERNATIEF — AUTOMATISCH</div>
              <h3 className="font-display text-xl text-ll-cream mb-2">Via Kiwi Browser of Firefox Mobile</h3>
              <p className="text-sm mb-2">Beide accepteren onze hele Chrome-extensie. Loading via developer mode:</p>
              <ol className="list-decimal pl-6 space-y-2 text-sm">
                <li>Clone de <a href="https://github.com/ErikWeertsOG/nts-vibe-checker" target="_blank" rel="noopener" className="text-ll-cyan underline">repo</a></li>
                <li>In Kiwi: <em>Menu → Extensions → Developer mode → Load from .zip</em></li>
                <li>Selecteer de <code>extension/</code> map</li>
              </ol>
            </section>
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-ll-indigo">
          <p className="text-xs text-ll-cream/50 font-body">
            Data komt live van deze site. Updates aan de scores (bv. handmatige overrides) verschijnen automatisch in de overlay — geen herinstallatie nodig.
          </p>
        </div>
      </div>
    </div>
  );
}
