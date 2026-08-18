# SafeVision AI — Dashboard

React + TypeScript + Tailwind front end for the Industrial PPE Safety Monitoring
system. It talks to the FastAPI backend in `../api` and serves the supervisor
operations center: live cameras, the violation review queue, evidence, reports,
analytics and the value stream.

## Prerequisites

| Tool        | Version   | Why                                    |
| ----------- | --------- | -------------------------------------- |
| Node.js     | 18+       | Build and run the front end            |
| npm         | 9+        | Package manager (ships with Node.js)   |
| Python      | 3.10+     | Run the FastAPI backend (`../api`)     |

Check your versions:

```bash
node -v && npm -v
python --version
```

## Quick Start

From the `frontend/` directory, run these steps in order:

```powershell
# 1. Install front-end dependencies
npm install

# 2. Start the FastAPI backend (Terminal 1) — serves the API on :8000
cd ..
python -m api --reload

# 3. Start the Vite dev server (Terminal 2) — serves the dashboard on :5173
cd frontend
npm run dev
```

Then open:

- **Dashboard** → http://localhost:5173
- **API docs (Swagger)** → http://127.0.0.1:8000/docs

The dev server proxies `/api` requests to `http://127.0.0.1:8000`, so both
terminals must be running for the dashboard to show live data.

### Alternative: single-server production mode

Build the front end once, and FastAPI serves everything from one port — no dev
server needed:

```powershell
# 1. Install dependencies
cd frontend
npm install

# 2. Type-check and emit the production bundle into dist/
npm run build

# 3. Go back to the project root and start the backend
cd ..
python -m api
```

Open **http://127.0.0.1:8000** — the built dashboard is served automatically
whenever `frontend/dist/` exists.

## Available Scripts

Run these from the `frontend/` directory:

| Command               | What it does                                              |
| --------------------- | --------------------------------------------------------- |
| `npm run dev`         | Start the Vite dev server on http://localhost:5173 (hot reload) |
| `npm run build`       | Type-check (`tsc --noEmit`) then build to `dist/`         |
| `npm run preview`     | Preview the production build locally (after `npm run build`) |
| `npm run typecheck`   | Type-check only, no output                                |

### One-shot dev workflow

In two separate terminals from the project root:

```powershell
# Terminal 1 — backend
python -m api --reload

# Terminal 2 — front end
cd frontend
npm run dev
```

## Project Layout

| Path                          | Purpose                                             |
| ----------------------------- | --------------------------------------------------- |
| `src/main.tsx`                | React entry point                                   |
| `src/App.tsx`                 | Route definitions                                   |
| `src/index.css`               | Global styles, design tokens (single dark theme)    |
| `src/lib/api.ts`              | Fetch wrapper, media and export URL helpers         |
| `src/lib/hooks.ts`            | React Query bindings and the polling intervals      |
| `src/lib/types.ts`            | Wire types mirroring the API responses              |
| `src/lib/format.ts`           | All display formatting (dates, percentages, sizes)  |
| `src/components/ui/primitives.tsx` | Panels, badges, buttons, inputs, modal, icons   |
| `src/components/charts/charts.tsx` | SVG trend, bar, column and meter charts          |
| `src/components/layout/`      | Sidebar, top bar, page frame                        |
| `src/components/domain/`      | Stat tiles, camera tiles, incident cards            |
| `src/pages/`                  | One file per route                                  |
| `dist/`                       | Production build (served by FastAPI)                |

## Tech Stack

- **React 18** + **TypeScript** — UI and type safety
- **Vite 5** — dev server and build tooling
- **Tailwind CSS 4** — styling
- **React Router 6** — routing
- **@tanstack/react-query** — server state, caching, polling

## Design Constraints

- **Dark, single theme.** The product runs on a control-room monitor; a theme
  toggle is not a feature there. Colours are declared once in `src/index.css`.
- **Status is never colour alone.** Every status dot and badge carries a text
  label so the meaning survives colour-blind vision and a washed-out panel.
- **No fabricated values.** Where the backend has no data, the UI shows an
  em dash and an explanation rather than a plausible-looking number.
- **The page never scrolls sideways.** Wide tables scroll inside their own
  container.
- Camera grid columns follow the brief: 1 on tablet, 2 on laptop, 4 on desktop.

## Troubleshooting

| Problem                                  | Fix                                              |
| ---------------------------------------- | ------------------------------------------------ |
| Dashboard shows no data / network errors | Backend not running — start `python -m api --reload` in Terminal 1 |
| Port 5173 already in use                 | Vite picks the next free port automatically; use that URL |
| `npm install` fails                      | Upgrade Node to 18+ and retry                    |
| API responses come from an older build   | Delete `dist/` and rebuild with `npm run build`  |
