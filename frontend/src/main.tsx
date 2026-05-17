import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// SW disabled — kill switch deploy. Old versions of /sw.js trapped
// users on stale builds. We still serve /sw.js (now a self-unregister
// kill switch) so existing installs purge themselves. Re-enable later
// once we are sure the cache strategy is solid.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.getRegistrations().then((regs) => {
    for (const r of regs) r.update();
  }).catch(() => {});
}
