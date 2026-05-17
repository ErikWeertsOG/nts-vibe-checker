// ==UserScript==
// @name         NTS Vibe Checker — Lowlands 2026
// @namespace    https://nts-vibe-checker.vercel.app
// @version      0.1.0
// @description  Toont NTS-vibe score badges op lowlands.nl. Werkt automatisch op elke acts-pagina.
// @author       Erik Weerts
// @match        https://lowlands.nl/*
// @match        https://www.lowlands.nl/*
// @run-at       document-idle
// @grant        none
// @require      https://nts-vibe-checker.vercel.app/inject.js
// @updateURL    https://nts-vibe-checker.vercel.app/ntsvc.user.js
// @downloadURL  https://nts-vibe-checker.vercel.app/ntsvc.user.js
// @homepageURL  https://nts-vibe-checker.vercel.app
// @icon         https://nts-vibe-checker.vercel.app/icon-192.png
// ==/UserScript==

// All logic lives in inject.js. The @require directive above pulls it in
// at install time. To get updates, just re-run "Update scripts" in your
// userscript manager (or it auto-updates daily by default).
