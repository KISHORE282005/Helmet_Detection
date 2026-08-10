# SafeVision AI — Dashboard

React + TypeScript + Tailwind front end for the Industrial PPE Safety Monitoring
system. It talks to the FastAPI backend in `../api`.

## Development

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api to 127.0.0.1:8000
```

Run the API in a second terminal so the proxy has a target:

```bash
cd ..
python -m api --reload
```

## Production build

```bash
npm run build        # type-checks, then emits dist/
```

FastAPI serves `dist/` automatically when it exists, so after a build the whole
application is available from `http://127.0.0.1:8000` on its own.

## Layout

| Path | Purpose |
|---|---|
| `src/lib/api.ts` | fetch wrapper, media and export URL helpers |
| `src/lib/hooks.ts` | React Query bindings and the polling intervals |
| `src/lib/types.ts` | wire types mirroring the API responses |
| `src/lib/format.ts` | all display formatting (dates, percentages, sizes) |
| `src/components/ui/primitives.tsx` | panels, badges, buttons, inputs, modal, icons |
| `src/components/charts/charts.tsx` | SVG trend, bar, column and meter charts |
| `src/components/layout/` | sidebar, top bar, page frame |
| `src/components/domain/` | stat tiles, camera tiles, incident cards |
| `src/pages/` | one file per route |

## Design constraints

- **Dark, single theme.** The product runs on a control-room monitor; a theme
  toggle is not a feature there. Colours are declared once in `src/index.css`.
- **Status is never colour alone.** Every status dot and badge carries a text
  label so the meaning survives colour-blind vision and a washed-out panel.
- **No fabricated values.** Where the backend has no data, the UI shows an
  em dash and an explanation rather than a plausible-looking number.
- **The page never scrolls sideways.** Wide tables scroll inside their own
  container.
- Camera grid columns follow the brief: 1 on tablet, 2 on laptop, 4 on desktop.
