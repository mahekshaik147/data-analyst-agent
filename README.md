# Data Analyst Agent

A responsive analytics workspace for natural-language analysis, SQL inspection, dataset browsing, and Text-to-SQL evaluation. The frontend is designed to connect to a separate FastAPI service; it does not fabricate analysis results when the service is unavailable.

## Run locally

```sh
npm install
cp .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` in `.env` to the FastAPI service origin when it is not served from the same origin. The expected endpoints are `GET /api/health`, `GET /api/schema`, `GET /api/datasets`, `POST /api/analyze`, `POST /api/query`, `GET /api/evaluation`, and `POST /api/evaluation/run`. CORS must allow the frontend origin if the service uses a different origin.

No LLM credentials belong in the frontend. Keep provider credentials and SQL execution safeguards in the Python service.

## Frontend scripts

- `npm run dev` — local development
- `npm run build` — production build
- `npm test` — unit and routing tests