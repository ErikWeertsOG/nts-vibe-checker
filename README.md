# NTS Vibe Checker

Score elke Lowlands-act op NTS-vibe. Statische web-app + data pipeline.

## Hoe werkt het

1. **Pipeline** (Python, lokaal) scraped Lowlands lineup + alle NTS shows, matcht artiesten, scoort 0–100, genereert NTS-stijl blurbs via Claude API, schrijft naar `frontend/public/acts.json`.
2. **Frontend** (Vite + React) laadt die JSON, toont een gesorteerde lijst met filters en een "waar moet ik nu heen?"-modus.

## Pipeline runnen

```bash
cd pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python build.py
```

Output: `frontend/public/acts.json`

## Frontend dev

```bash
cd frontend
npm install
npm run dev
```

## Scoring rubric (strict NTS)

| Signal | Score |
|---|---|
| Eigen NTS show (resident) | 90–100 |
| Guest-show / vaak op NTS | 70–89 |
| Genoemd in show-descriptions / af en toe gedraaid | 40–69 |
| Lichte sporen op NTS | 15–39 |
| Niets gevonden | 0 |
