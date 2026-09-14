# SS459 Frontend (Phase 0 — Foundation)

React + Vite + TypeScript + Tailwind. RTL / Persian shell.

> Phase 0 contains **no business UI** — only the app shell, routing,
> the typed API client (with error-envelope handling) and a Dashboard
> page that proves frontend ↔ backend wiring via `/health`.

## Quickstart

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (proxies API paths to :8000)
```

Backend must run on `http://localhost:8000`
(see `../backend/README.md`), or set `VITE_BACKEND_URL` in `.env`.

```bash
npm run typecheck  # tsc --noEmit
npm run build      # typecheck + production build
npm run preview    # serve the production build on :4173
```

## Structure (spec 12)

```
src/
  main.tsx  App.tsx  index.css
  pages/       # route shells (Dashboard + placeholders)
  components/  # shared UI (Layout/nav)
  features/    # dashboard, planner, tests, progress, books,
               # academics, rewards, settings (filled Phase 1+)
  api/         # typed client + endpoint modules
  hooks/ types/ utils/
```

## API client

All requests go through `src/api/client.ts`, which throws `ApiError`
parsed from the backend error envelope (`{error: {code, message, details}}`).
URLs are relative by default; the Vite dev server proxies known contract
paths to the backend (see `vite.config.ts`) so there are no CORS issues.
