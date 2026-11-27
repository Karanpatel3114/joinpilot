# Deploying JoinPilot for free

The API runs on Render's free web service and the console on Vercel's free Hobby plan (decision D-036). Neither needs a payment method. **Never add a card to either account:** without one, the free plans cannot bill you.

What to expect from free hosting:
- The API sleeps after 15 minutes without traffic. The next visit waits about a minute while it wakes.
- The API's disk is wiped on every restart, so uploads and runs last only until then. Demo mode (M12.2) loads the sample project again at startup.

## 1. API on Render

1. Sign in at [render.com](https://render.com) with **Continue with GitHub**, and allow Render to see the `joinpilot` repository.
2. Choose **New → Blueprint**, pick the repository and the `main` branch. Render reads [`render.yaml`](../render.yaml) and proposes one free web service, `joinpilot-api`.
3. Render asks for two values:
   - `CORS_ORIGINS`: the console's address as a JSON list. If you don't know it yet, enter `["https://joinpilot.vercel.app"]` and correct it after step 2.
   - `GEMINI_API_KEY`: a free key from [aistudio.google.com](https://aistudio.google.com/apikey), or leave it empty. Without a key, runs use the deterministic path and the Ask tab says a key is needed.
4. Click **Apply**. The first build takes about 10 minutes. When it is live, open `https://<service>.onrender.com/health`; it returns `{"status":"ok",...}`.

## 2. Console on Vercel

1. Sign in at [vercel.com](https://vercel.com) with **Continue with GitHub**.
2. **Add New → Project**, import `joinpilot`, and set **Root Directory** to `web`. Keep **Include files outside the root directory** switched on (the default): the build type-checks tests that read `shared/fixtures/`. Vercel reads [`web/vercel.json`](../web/vercel.json) for the build.
3. Under **Environment Variables**, add `VITE_API_URL` = your Render address, such as `https://joinpilot-api.onrender.com` (no trailing slash). If it is not that exact address, change `connect-src` in the Content-Security-Policy in [`web/vercel.json`](../web/vercel.json) to match, or the browser will block every API call.
4. Click **Deploy**. Note the address Vercel gives you, such as `https://joinpilot.vercel.app`.
5. If that address differs from what you entered for `CORS_ORIGINS` on Render, update it under the Render service's **Environment** tab. Render restarts the API with the new value.

Both services redeploy automatically on every push to `main`.

## 3. Check it

```bash
uv run python infra/smoke_api.py https://<service>.onrender.com     # API: create, load, run, approve, checks
cd web && E2E_BASE_URL=https://<project>.vercel.app npx playwright test happy-path
```

Once the console works, check the rate limiter sees real visitor addresses: the Blueprint sets `LIMITS__FORWARDED_HOPS=1` because Render's proxy appends the visitor's address to `X-Forwarded-For`. If Render's logs show one address for every visitor, raise it by one.

## Settings worth knowing

Every setting is described in [`.env.example`](../.env.example). The Blueprint sets the ones the free instance needs: in-process jobs, SQLite, a 256 MB DuckDB limit, one DuckDB thread, the small sample only and 10 MB uploads. Rate limits (`LIMITS__*`) protect the free model quota. To run with Postgres and Redis instead, set `DATABASE_URL`, `REDIS_URL` and `JOBS_MODE=arq`, as Docker Compose does.
