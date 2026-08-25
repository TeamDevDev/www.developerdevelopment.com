# Runbook: Quarto → Cloudflare Workers migration checkpoints

> **Fast path:** `scripts/migrate-to-cloudflare.py` (in the reference
> repository) automates every stage below through the Cloudflare API:
> `uv run scripts/migrate-to-cloudflare.py --config <config> --stage all`
> from inside the target repository. The checkboxes below are the manual
> equivalent and double as the verification record.

Work through these stages **in order**. Each stage has a command to run and
a check that must pass before moving on. "Site values" column:

| Value | developerdevelopment | securitysynapse |
| ----- | -------------------- | --------------- |
| Worker | `www-developerdevelopment-com` | `www-securitysynapse-org` |
| Branch | `master` | `main` |
| Build | `uv run quarto render --profile optimize` | `uv run --with jupyter --with cryptography quarto render` |
| Zone | `developerdevelopment.com` | `securitysynapse.org` |

## 0. Prerequisites

- [ ] API token created with Workers Scripts / Static Assets / Workers
  Routes → **Edit** permissions, scoped to the correct account.
- [ ] `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` secrets added to
  both GitHub repositories.
- [ ] `wrangler.toml` is committed and tracked (not in `.gitignore`) in
  both repos.

## 1. Reproduce the build locally (before enabling CI)

- [ ] `developerdevelopment`: `uv run quarto render --profile optimize`
- [ ] `securitysynapse`: `uv run --with jupyter --with cryptography quarto render`
- [ ] `_site/index.html` exists in each repo.
- [ ] Serve and spot-check: `cd _site && python -m http.server 8000`
  then open a few pages and confirm assets load.

## 2. Deploy (CI, or local wrangler)

- [ ] Push the workflow + `wrangler.toml` to the branch.
- [ ] GitHub Actions "Deploy to Cloudflare Workers" step is **green**.
  (Locally: `wrangler deploy` from the repo root.)
- [ ] `*.workers.dev` URL returns your site (find the exact subdomain in
  the wrangler output / dashboard):
  `curl -sI https://www-developerdevelopment-com.<sub>.     workers.dev | head -n1`
  → expect `200`

## 3. Bind the custom domains (apex first — it is the live host)

Today both sites `301`-redirect `www` → apex and serve from the **apex**, so
the apex is *not* optional — it is the primary hostname. A Custom Domain
binding must own its DNS record, so the Netlify record on each hostname is
deleted as part of the binding.

- [ ] Add the apex (`developerdevelopment.com`) as a Custom Domain on the
  Worker (dashboard, or uncomment the `[[routes]]` block and redeploy).
  If Cloudflare reports a conflicting DNS record, delete the Netlify
  apex `A` record (`75.2.60.5`) and complete the binding. Expect a brief
  (seconds-to-minutes) window — schedule at a low-traffic time.
- [ ] `curl -sI https://developerdevelopment.com | head -n1` → `200`
- [ ] Add `www.developerdevelopment.com` as a Custom Domain the same way
  (delete the Netlify CNAME if it conflicts). `www` only 301-redirects
  to the apex today, so its switchover causes no user-visible outage.
- [ ] DNS no longer points at Netlify:
  `dig +short developerdevelopment.com` → Cloudflare IPs, not `75.2.60.5`
  `dig +short www.developerdevelopment.com`
  → should no longer show `developerdevelopment.netlify.app`
- [ ] HTTPS responds on the real hostname:
  `curl -sI https://www.developerdevelopment.com | head -n1` → `200`
- [ ] Page actually renders (real HTML, not a redirect):
  `curl -s https://www.developerdevelopment.com | grep -i "<title>"`

> Note: after migration both hostnames serve the site directly; the old
> `www` → apex `301` redirect no longer happens. Add a Cloudflare Redirect
> Rule (`www` → apex) if you want it back — optional, cosmetic.

## 4. Content / behavior checks

- [ ] `developerdevelopment` serves the Quarto 404 page for an unknown path
  (`not_found_handling = "404-page"` is set in its `wrangler.toml`):
  `curl -s https://developerdevelopment.com/this-does-not-exist |     grep -i "<title>"` → `Sorry, this Page is Not Available!`
- [ ] `securitysynapse` has no custom 404 page, so a plain `404` is
  **expected** (Netlify's default "Page not found" page goes away):
  `curl -sI https://securitysynapse.org/this-does-not-exist |     head -n1` → `404`
- [ ] A known asset loads (e.g., a stylesheet or icon):
  `curl -sI https://developerdevelopment.com/styles.css | head -n1`
- [ ] Navbar routes (blog / schedule / syllabus) resolve — spot-check a few.
- [ ] Repeat stages 3–4 for `securitysynapse.org`
  (`www-securitysynapse-org` worker; apex A record `75.2.60.5` and
  `www` CNAME `securitysynapse.netlify.app` are the Netlify records).

## 5. Optional: restore the `www` → apex canonical redirect

- [ ] If you want the pre-migration behavior where `www` 301-redirects to
  the apex, add a Cloudflare Redirect Rule for
  `www.<site>/<path>` → `https://<site>/<path>` in the dashboard
  (Rules → Redirect Rules). Purely cosmetic/SEO — skip it if both
  hostnames serving the same content is fine.

## 6. Clean up Netlify (only after all checks pass)

- [ ] Remove any remaining old Netlify `A` / `CNAME` records from each zone
  (normally they were already replaced during the stage-3 binding).
- [ ] Delete the old Netlify apps.
- [ ] Re-run the `dig` + `curl` checks once more to confirm nothing broke.

## Rollback

Re-point DNS back to Netlify until the Worker is fixed:

- Restore the apex `A` record to `75.2.60.5`.
- Restore the `www` CNAME to `<site>.netlify.app` (`developerdevelopment`
  / `securitysynapse`).

Keep the Netlify app alive until every box above is checked.
