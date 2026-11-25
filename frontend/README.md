# VIO frontend (Voice It Out)

React + Vite + React Router. Plain CSS with all colours in one token block (`src/styles/tokens.css`).

## Run
```powershell
npm install
copy .env.example .env.local
npm run dev
```
Build: `npm run build` (output in `dist/`).

## Deploy (Vercel or Netlify)
- Root directory: `frontend`. Build command: `npm run build`. Output: `dist`.
- Single page app routing is already configured (`vercel.json` and `public/_redirects`).
- Set `VITE_API_BASE_URL`, `VITE_API_MODE` and `VITE_API_CREDENTIALS` as environment variables, then redeploy.
- Leave `VITE_API_MODE=mock` until the backend is ready. Mock mode shows a banner on every page.
- Cookie sessions across two domains (frontend and API) can fail. Confirm the approach with the backend developer first.

## What is built
| Route | State |
|---|---|
| `/` | Built (onboarding page) |
| `/sign-up` | Built (UI only; email verification/account creation not connected) |
| `/dashboard` | Built. Response shape is ASSUMED, see `src/shared/api/dashboardContract.js` |
| `/lecturer/access`, `/lecturer/findings/:findingId`, `/lecturer/notices` | Built as UI only (frontend dev 2). No backend wiring yet |
| everything else | Placeholder page that says it is not built |

## Structure
- `src/shared/api`: single API client, live adapter (endpoints from `VIO_HACKATHON_SPECIFICATION.md`), mock adapter, safe error handling. Anything the spec does not define is listed in `UNRESOLVED` in `live.js`.
- `src/shells`: public, student and secure-link shells. The secure-link shell is shared by lecturer and authority pages.
- `src/pages`: one folder per area. `src/styles`: `landing.css`, `tokens.css`, `base.css`, `dashboard.css`, `secure.css`, `extras.css`.

## Rules the code follows
Never invent endpoints or fields. No fake data in live mode. Never retry a write automatically. Never log tokens, emails or report text. The backend supplies status, descriptions and available actions; the frontend never computes them.

## Lecturer pages boundary
The lecturer pages do not authenticate anyone, load real findings, submit replies or invent notices. Connect them only after the exact lecturer API contract is agreed. The spec lists `POST /lecturer/session`, `/lecturer/class-notices` and `/lecturer/replies`, but not how a private link is redeemed.
