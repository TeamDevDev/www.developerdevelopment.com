# Migrating Quarto Sites to Cloudflare Workers

This document explains how to convert two other Quarto web sites so that they
are deployed to, and served by, **Cloudflare Workers**, exactly like I previously
did for the site deployed at `www.gregorykapfhammer.com`.

## Sites In Scope

| Site | Repository | Branch | Current host |
| ----------------------------------- | ----------------------------------- | ------ | ------------ |
| `www.developerdevelopment.com` | `TeamDevDev/www.developerdevelopment.com` | `master` | Netlify |
| `www.securitysynapse.org` | `SecuritySynapse/www.securitysynapse.org` | `main` | Netlify |

Both domains are **already hosted on Cloudflare** for DNS, so no domain/zone
transfer is required. That is the single biggest prerequisite and it is done.

## How the Working Reference Site Works

`www.gregorykapfhammer.com` is served by a **Cloudflare Worker that owns static
assets** — *not* Cloudflare Pages. The mechanism is:

1. **Quarto renders the site** into a `_site/` directory.
1. A **`wrangler.toml`** file at the repo root describes the Worker:
   ```toml
   name = "www-gregorykapfhammer-com"
   compatibility_date = "2026-01-31"

   [assets]
   directory = "./_site"
   ```
   The `[assets] directory = "./_site"` line is what turns the Worker into a
   static-asset server: every request is answered from `_site/`, with no Worker
   script required.
1. A **GitHub Actions workflow** (`.github/workflows/publish.yml`) runs the
   Quarto build and then deploys with Cloudflare's `wrangler` tool:
   ```yaml
   - name: Deploy to Cloudflare Pages
     uses: cloudflare/wrangler-action@v3
     with:
       apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
       accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
       command: deploy
       gitHubToken: ${{ secrets.GITHUB_TOKEN }}
   ```
   `wrangler deploy` reads `wrangler.toml`, uploads `_site/`, and publishes the
   Worker. (The step name still says "Pages" but the action actually runs
   `wrangler deploy`, which pushes the Worker + assets.)

So the whole pipeline is: **push → GitHub Actions renders Quarto → wrangler
uploads `_site/` → Cloudflare Workers serves it at your domain.**

## Can This Be Automated?

**Yes — all of it.** You do not need to "click around" the Cloudflare
dashboard. The only step that *no tool can automate* is creating the
Cloudflare API token itself (Cloudflare requires it in the dashboard);
everything else — secrets, deploy, DNS, domain binding, verification,
rollback — is a terminal command.

### Option 0 — The migration script (one command per site)

`scripts/migrate-to-cloudflare.py` in this repository automates the whole
runbook through the Cloudflare API and the `gh` CLI. It uses only the Python
standard library, so `uv run` needs no installs.

To migrate one of the target sites, copy the script, its configs, and the
docs into that site's repository (everything is self-contained), then run
the script from inside it:

```bash
# from the reference repository:
cp scripts/migrate-to-cloudflare.py \
   ~/working/web/www.developerdevelopment.com/scripts/
cp -r scripts/migrate-configs \
   ~/working/web/www.developerdevelopment.com/scripts/
cp MIGRATE.md RUNBOOK.md ~/working/web/www.developerdevelopment.com/

# then, from inside the target site's repository:
export CLOUDFLARE_API_TOKEN=...   # created once in the dashboard
export CLOUDFLARE_ACCOUNT_ID=...
uv run scripts/migrate-to-cloudflare.py \
  --config scripts/migrate-configs/developerdevelopment.toml \
  --stage all
```

(`uv run` manages the developerdevelopment repository's project dependencies
and runs the Quarto build in the same environment.)

Every action is labeled as it runs, so you always know what the script is
doing on your machine and your Cloudflare account:

- `[shell] $ ...` — an external program is being executed (quarto, wrangler,
  gh, dig, curl), with its own output streamed below
- `[cloudflare] METHOD /path` — a Cloudflare API request, including the
  request body and the HTTP result (`-> HTTP 200 OK` or the API's error
  message), so a failed deploy shows exactly what Cloudflare said
- `[file] wrote ...` — a file was written or backed up on disk
- stages that change DNS (`domain`, `rollback`, `cleanup`) prompt for
  confirmation first (pass `--yes` to skip)

Stages (run individually with `--stage <name>`, or as `all`):

| Stage | What it does |
| ---------- | ------------ |
| `check` | verifies tools, credentials, and current DNS state |
| `generate` | writes `wrangler.toml` + `.github/workflows/publish.yml` |
| `secrets` | `gh secret set` the two Cloudflare secrets on the repo |
| `build` | runs the site's render command (mirrors CI) |
| `deploy` | `wrangler deploy` uploads `_site/` as the Worker's assets |
| `domain` | binds apex + `www` via the Cloudflare API, replacing the Netlify DNS records (snapshots DNS first for rollback) |
| `verify` | runs the RUNBOOK.md `dig`/`curl` checks |
| `rollback` | restores the pre-migration DNS records from the snapshot |
| `cleanup` | deletes leftover Netlify DNS records |

Per-site settings (worker name, apex, render command, workflow setup steps)
live in small TOML files in `scripts/migrate-configs/`; adding another
Quarto site later means writing one new TOML file — no process knowledge
required. The script never commits or pushes; review the generated files
and push them yourself.

### Option 1 — GitHub Actions (matches the reference)

This is what the reference site does today and is the least work. `wrangler`
runs inside the workflow, so you need no local install. Every time you push to
the branch, GitHub builds the site and deploys it for you. The only dashboard
interaction is the *one-time* "add custom domain" step (see
[Bind the Custom Domain](#bind-the-custom-domain)) — or you can eliminate even
that by putting `[[routes]]` with `custom_domain = true` in `wrangler.toml` (see
[Automate the Domain Binding](#automate-the-domain-binding)).

### Option 2 — Install `wrangler` on this NixOS laptop

`wrangler` is the official Cloudflare CLI and it **is packaged in nixpkgs**.
Install it once with:

```bash
nix profile install nixpkgs#wrangler
```

(You can also use `npm install -g wrangler`, since Node v26 is already
installed. The nixpkgs version is currently 4.6x; npm has 4.12x.)

Then, from a site directory containing `wrangler.toml`:

```bash
quarto render                 # or: quarto render --profile optimize
wrangler login                # one-time OAuth browser login (interactive)
wrangler deploy
```

Put the `quarto render` + `wrangler deploy` pair in a small bash script and
deploy on demand. For fully scripted (non-interactive) use, export a token
instead of `wrangler login`:

```bash
export CLOUDFLARE_API_TOKEN=...   # from your API tokens page
export CLOUDFLARE_ACCOUNT_ID=...  # 32-char hex id from the dashboard URL
quarto render
wrangler deploy
```

### Option 3 — Python script driven by `uv`

Yes, this works too. `wrangler` itself is a Node tool (not a PyPI package), so a
Python script orchestrates the steps and shells out to the CLI. Because Node and
`npx` are already installed, you can invoke `wrangler` without installing it:

```python
# scripts/deploy.py — run with: uv run python scripts/deploy.py
import subprocess

def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)

run(["quarto", "render"])  # add --profile optimize if the site needs it
run(["npx", "wrangler", "deploy"])  # reads ./wrangler.toml; CF secrets in env
```

Save secrets as environment variables before running. `uv` manages nothing about
`wrangler` (it is not a Python dependency), but `uv run` is a convenient wrapper
for the orchestration script. `npx wrangler` will download the CLI on first
run; the cached binary is reused afterward.

> **Recommendation:** Use **Option 1 (GitHub Actions)** as the primary
> deployment mechanism — it is proven by the reference site, requires no local
> tooling, and keeps deploys reproducible. Use Option 2 (`nix profile install nixpkgs#wrangler`) for occasional manual/local deploys and testing. Option 3
> is best when you want extra orchestration logic in one Python script.

______________________________________________________________________

## Prerequisites (one-time, shared by both sites)

1. **On the Cloudflare dashboard**, create an **API token** for CI deploys:

   - Profile (top-right) → **My Profile** → **API Tokens** → **Create Token** →
     **Create Custom Token**.
   - Name it `quarto-site-deploy`.
   - Permissions (mind the scopes — `Workers Routes` and
     `Workers Custom Domains` are **Zone** permissions, not Account ones):
     - **Account** → **Workers Scripts** → **Edit** — this is the permission
       that uploads the Worker *and its static assets*; there is no separate
       "Static Assets" permission.
     - **User** → **Memberships** → **Read** — `wrangler` calls the
       `/memberships` endpoint to resolve your account; without this the
       deploy fails with an authentication error.
     - **Zone** → **Workers Routes** → **Edit** — only needed if you add
       zone-level routes in `wrangler.toml`.
     - **Zone** → **Workers Custom Domains** → **Edit** — only needed if you
       bind custom domains from `wrangler.toml` (`custom_domain = true`).
   - Account Resources: **Include** → your account.
   - Copy the token value immediately (shown once).

1. **Get your Account ID** (not your email/username). It is the long hex string
   in the dashboard URL: `https://dash.cloudflare.com/<ACCOUNT_ID>/...`.

1. **Add two secrets to each GitHub repository** that hosts the CI:

   - `Settings` → **Secrets and variables** → **Actions** → **New repository
     secret**.
   - `CLOUDFLARE_API_TOKEN` = the token from step 1.
   - `CLOUDFLARE_ACCOUNT_ID` = the hex id from step 2.

   Do this for `TeamDevDev/www.developerdevelopment.com` and for
   `SecuritySynapse/www.securitysynapse.org`.

______________________________________________________________________

## Site A — www.developerdevelopment.com

This site builds with **uv** and deploys to Cloudflare using the
`--profile optimize` profile (which runs `scripts/minify-files.py`). The
project dependencies are declared in `pyproject.toml` and locked in
`uv.lock`. A `wrangler.toml` has already been written into this repo's root.

### A1. Add `wrangler.toml`

Already created at `wrangler.toml` in this repo. It contains:

```toml
name = "www-developerdevelopment-com"
compatibility_date = "2026-08-25"

[assets]
directory = "./_site"
not_found_handling = "404-page"
```

Confirm it is committed and tracked (do not add it to `.gitignore`); it is
currently untracked in the local clone.

The `not_found_handling = "404-page"` line matters: by default a Worker with
static assets answers unknown paths with a bare, empty `404` — it does **not**
automatically serve the `404.html` that Quarto emits into `_site/`. (The
reference site originally omitted this option and served an empty 404 body;
its `wrangler.toml` now sets `not_found_handling = "404-page"` to fix that.)
With this setting, Workers serves `_site/404.html` for any missing path,
preserving the current Netlify behavior.

### A2. Replace the deploy step in `.github/workflows/publish.yml`

`publish.yml` should render with `uv run quarto render --profile optimize`
and then deploy with Wrangler. Replace the whole file's build section with:

```yaml
name: Publish

on:
  push:
    branches: [ master ]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out Repository
        uses: actions/checkout@v3
        with:
          submodules: true

      - name: Set up Quarto
        uses: quarto-dev/quarto-actions/setup@v2
        with:
          version: 1.5.56

      - name: Install Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Sync Python dependencies
        run: uv sync --locked

      - name: Render the Site (optimize profile)
        env:
          PYDEVD_DISABLE_FILE_VALIDATION: 1
        run: uv run quarto render --profile optimize

      - name: Deploy to Cloudflare Workers
        if: github.event_name == 'push'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: deploy
          gitHubToken: ${{ secrets.GITHUB_TOKEN }}
```

Notes:

- The `NETLIFY_AUTH_TOKEN` environment variable and `quarto publish netlify`
  are **removed**.
- Keep the `--profile optimize` flag so `_site/` is still minified exactly as
  it was under Netlify.
- `_site/` is already in `.gitignore`, so nothing to exclude.
- The `if: github.event_name == 'push'` guard keeps pull requests as
  build-only checks so a PR can never deploy to production. (The current
  `publish.yml` already publishes on `push` only, so the production flow is
  unchanged.)
- The repo also contains `.github/workflows/build.yml`, a second workflow
  that renders without publishing on pushes and PRs; leave it unchanged.
  Its PR runs keep giving you a build check after the migration.

### A3. Bind the custom domains (apex first — it is the live host)

**Important:** today `www.developerdevelopment.com` answers with a `301`
redirect to `developerdevelopment.com`, and the **apex is the host people
actually reach**. Both hostnames must be bound to the Worker — the apex is
not optional. After the first successful `wrangler deploy`, the Worker is
live on a `*.workers.dev` subdomain; then:

1. **Bind the apex `developerdevelopment.com` first.** Dashboard: Workers &
   Pages → your Worker (`www-developerdevelopment-com`) → **Settings** →
   **Domains & Routes** → **Add → Custom Domain** → enter
   `developerdevelopment.com`. Because the apex currently has a Netlify `A`
   record (`75.2.60.5`), Cloudflare will report a conflicting DNS record —
   delete the Netlify `A` record and add the Custom Domain. Expect a brief
   window (seconds to a few minutes) while the record is replaced; the site
   is fully live on the Worker once the binding is active. Do this at a
   low-traffic time.
1. **Then bind `www.developerdevelopment.com`** the same way (delete the
   Netlify CNAME if it conflicts). Downtime here does not matter: `www`
   only 301-redirects to the apex today.
1. **From code instead of the dashboard:** run the `domain` stage of
   `scripts/migrate-to-cloudflare.py`. It snapshots the current DNS records,
   removes only the recognized Netlify records, attaches each hostname with
   the supported Workers Custom Domains API fields, and verifies the binding
   before continuing. If the stage fails after DNS removal, use the saved
   snapshot with `--stage rollback`.

Note that with both hostnames bound to the same Worker, `www` serves the
site directly instead of 301-redirecting to the apex. Both URLs will work;
if you want the old canonical redirect back, add a Cloudflare Redirect Rule
(`www` → apex) after the migration is stable — it is a cosmetic/SEO nicety,
not a correctness issue.

### A4. Clean up the old Netlify records and app

- In practice the apex `A` record (`75.2.60.5`) and the `www` CNAME
  (`developerdevelopment.netlify.app`) are removed during the A3 binding,
  because a Custom Domain must own its hostname's DNS record. If either
  Netlify record is still present afterwards, delete it.
- Delete the old Netlify site (`developerdevelopment` / its `.netlify.app`
  project) once you have confirmed the Cloudflare URL responds correctly.

______________________________________________________________________

## Site B — www.securitysynapse.org

This site builds with a minimal uv workflow that provides `jupyter` and
`cryptography` through `uv run --with`, then deploys to Cloudflare. It uses
`execute.freeze: auto`, but `_freeze/` is **gitignored and not committed**
(`.gitignore` contains `_freeze`, and `git ls-files _freeze` is empty), so
CI re-executes the computational content on every build — the migration does
not change this. A `wrangler.toml` has already been written into this repo's
root.

### B1. Add `wrangler.toml`

Already created at `wrangler.toml` in this repo:

```toml
name = "www-securitysynapse-org"
compatibility_date = "2026-08-25"

[assets]
directory = "./_site"
```

Commit and track it; it is currently untracked in the local clone.

This site has **no custom 404 page** (there is no `404.qmd` and no
`404.html` in `_site/` — the "Page not found" page you see today is
Netlify's default), so `not_found_handling` is deliberately left at the
default: unknown paths will return a plain `404` from Workers, which is the
equivalent behavior. If you later add a `404.qmd`, also add
`not_found_handling = "404-page"` to `[assets]`.

### B2. Replace the deploy step in `.github/workflows/publish.yml`

`publish.yml` currently ends with `quarto publish netlify`. Replace the build
section with:

```yaml
name: Publish

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out Repository
        uses: actions/checkout@v3
        with:
          submodules: true

      - name: Set up Quarto
        uses: quarto-dev/quarto-actions/setup@v2
        with:
          version: 1.5.56

      - name: Install Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Render the Site
        run: uv run --with jupyter --with cryptography quarto render

      - name: Deploy to Cloudflare Workers
        if: github.event_name == 'push'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: deploy
          gitHubToken: ${{ secrets.GITHUB_TOKEN }}
```

Notes:

- `NETLIFY_AUTH_TOKEN` and `quarto publish netlify` are removed.
- The current workflow keeps its `pull_request` trigger (so PRs still get a
  build check), but the `if: github.event_name == 'push'` guard on the
  deploy step means a pull request can never deploy to production.
- `uv run --with jupyter --with cryptography quarto render` matches the current
  build. Because `_freeze/` is not committed, CI re-executes the computational
  content on every build — exactly what happens today, so nothing changes.
- `_site/` stays ignored in `.gitignore`. Do not "fix" the `_freeze` ignore
  entry unless you deliberately want to commit frozen results for faster,
  more reproducible CI builds.
- Add the two Cloudflare secrets to the
  `SecuritySynapse/www.securitysynapse.org` repository (see
  [Prerequisites](#prerequisites)).

### B3. Bind the custom domains (apex first — it is the live host)

Same situation as Site A: today `www.securitysynapse.org` 301-redirects to
`securitysynapse.org`, and the apex is the host people actually reach. Bind
**both** hostnames to the `www-securitysynapse-org` Worker — the apex
`securitysynapse.org` first (deleting the Netlify `A` record `75.2.60.5` when
Cloudflare reports the conflict), then `www.securitysynapse.org` (deleting
the Netlify CNAME if it conflicts). Use the dashboard's **Domains & Routes**
page, or uncomment the `[[routes]]` blocks in `wrangler.toml` and redeploy.

As with Site A, `www` will serve the site directly instead of redirecting to
the apex; add a Cloudflare Redirect Rule afterwards if you want the canonical
redirect back.

### B4. Clean up old Netlify records and app

The Netlify `A`/`CNAME` records are normally removed during the B3 binding;
delete any that remain, and delete the old Netlify site once the Cloudflare
URL responds correctly.

______________________________________________________________________

## Binding the real domain vs. the workers.dev URL

When you deploy with `wrangler.toml` and no `worker` script, the Worker is
immediately reachable at:

```
https://www-developerdevelopment-com.<your-subdomain>.workers.dev
https://www-securitysynapse-org.<your-subdomain>.workers.dev
```

Use these URLs to sanity-check the build before you flip the custom domain. The
users never see them; the Custom Domain step is what makes the real hostname
serve the Worker.

______________________________________________________________________

## Local testing before you deploy

For either site, from its directory:

```bash
# 1. Build locally (mirrors what CI will do)
#    devdev:   uv run quarto render --profile optimize
#    securitysynapse: uv run --with jupyter --with cryptography quarto render

# 2. Serve the generated _site and click around
cd _site && python -m http.server 8000
# open http://localhost:8000

# 3. Preview with wrangler (optional; needs nixpkgs/npm wrangler installed)
wrangler dev
```

`wrangler dev` serves `_site/` exactly as the deployed Worker will, which is
the best local approximation of the production behavior. (Local mode has
been the default since wrangler v3 — do not pass the deprecated `--local`
flag.)

______________________________________________________________________

## Verification after migration

1. Push the updated workflow + `wrangler.toml` to the site's branch. The GitHub
   Action should show a green "Deploy to Cloudflare Workers" step.
1. Confirm the `*.workers.dev` URL returns your site's HTML.
1. After binding the custom domains, visit `https://developerdevelopment.com`
   and `https://www.developerdevelopment.com` (and the securitysynapse
   equivalents). Check:
   - `curl -I https://developerdevelopment.com` returns `200` / `HTTP/2`.
   - `developerdevelopment`: unknown paths serve the Quarto 404 page
     ("Sorry, this Page is Not Available!") because
     `not_found_handling = "404-page"` is set in its `wrangler.toml`.
     `securitysynapse`: a plain `404` is expected — the site has no custom
     404 page, and Netlify's default "Page not found" page simply goes away.
   - All asset links (`/blog/...`, `/syllabus/...`, CSS/JS) resolve — Quarto's
     relative-path output works unchanged because it is served from the doc
     root just like Netlify.
1. Once happy, remove the Netlify DNS records and delete the Netlify app.

> Work through the staged checks in **RUNBOOK.md** — it has the exact
> `dig` / `curl` commands and checkboxes for every stage, including the
> DNS handoff and cleanup.

______________________________________________________________________

## Rollback

The old Netlify site still exists and its DNS was pointed at Netlify until step
[A4/B4]. If the Worker deploy has a problem:

1. Re-point the Cloudflare DNS `A`/`CNAME` records back to Netlify (or
   re-enable the Netlify automatic deploy), or
1. Remove the Worker custom-domain binding and keep the Worker on
   `*.workers.dev` until it is fixed.

You are never locked in; the migration is reversible until you delete the
Netlify site.

______________________________________________________________________

## Per-site cheat sheet

| Item | developerdevelopment | securitysynapse |
| ---------------------------- | ------------------------------ | -------------------------- |
| Worker name | `www-developerdevelopment-com` | `www-securitysynapse-org` |
| Git repo | `TeamDevDev/www.developerdevelopment.com` | `SecuritySynapse/www.securitysynapse.org` |
| Branch | `master` | `main` |
| Build command | `uv run quarto render --profile optimize` | `uv run --with jupyter --with cryptography quarto render` |
| Deploy action | `cloudflare/wrangler-action@v3`, `command: deploy` | same |
| Assets dir | `./_site` | `./_site` |
| Custom domain(s) | apex + `www` (apex is the live host) | apex + `www` (apex is the live host) |
| 404 handling | `not_found_handling = "404-page"` (has `404.html`) | default plain `404` (no custom page) |
| Netlify record cleanup | apex A + www CNAME replaced at binding, delete app | apex A + www CNAME replaced at binding, delete app |

______________________________________________________________________

## Risks and Mitigations

These are the realistic failure modes for this migration, ordered by
likelihood, with a mitigation for each. None of them is destructive
because the old Netlify apps keep serving until you delete them.

### 1. DNS / custom-domain handoff during the switch (highest risk)

Both `www.*` hosts are CNAMEs to Netlify that currently `301`-redirect to
the **apex**, and both apex domains point at `75.2.60.5` (Netlify's load
balancer). The apex — not `www` — is the host people actually reach, so the
apex **must** be bound to the Worker; a migration that binds only `www`
and then removes the Netlify records would take the primary domain down.

- A Custom Domain binding must own its hostname's DNS record, so the
  Netlify record on that hostname has to be deleted as part of the binding.
  This means a brief window (seconds to a few minutes) of apex downtime
  while the record is replaced — schedule it at a low-traffic time.
- Deleting the Netlify record *before* the Worker binding exists (and
  without immediately adding the binding) leaves the hostname resolving
  to nothing.
- `www` is the safe second step: it only 301-redirects to the apex today,
  so its switchover causes no user-visible outage.

**Mitigation:** verify the `*.workers.dev` URL first, then bind the apex
(delete the `75.2.60.5` `A` record when Cloudflare reports the conflict,
then complete the binding), confirm `https://<apex>` serves the site, then
bind `www` the same way. Keep the Netlify app alive until everything checks
out so DNS can be pointed back if needed.

### 2. `custom_domain = true` routes (only if uncommented)

Requires the zone to be on the same Cloudflare account as the API token,
and the hostname must not already be bound to another Worker. Otherwise
`wrangler deploy` fails with a clear error.

**Mitigation:** these blocks are commented out by default in both
`wrangler.toml` files. Prefer the dashboard for the first binding.

### 3. API token misconfiguration (classic first-run friction)

Token scoped to the wrong account, missing the **Account → Workers
Scripts → Edit** or **User → Memberships → Read** permission, or a
wrong/typo'd Account ID. This only fails the CI step (not destructive) but
is the most common first-run issue.

**Mitigation:** double-check the token's Account Resources and the 32-char
hex Account ID before the first deploy.

### 4. Build-environment drift in CI

Low risk, because CI runs exactly the render commands Netlify already ran
(uv + `--profile optimize` for developerdevelopment; uv-provided
jupyter/cryptography for securitysynapse). If the sites execute Jupyter code cells
that need native libraries not on the GitHub runner, rendering could fail
or differ. Neither target uses submodules, so there is no submodule-
checkout risk (that only affects the reference site, which uses
submodules for its bibliography).

**Mitigation:** keep the existing build commands; verify the generated
`_site/` matches a locally rendered copy before relying on it.

### 5. Static-asset behavior differences vs Netlify

Neither site has `netlify.toml`, `_redirects`, `_headers`, or Netlify
Forms, so those features need no migration. Three check items remain:

- `404.html` serves for unknown paths on `developerdevelopment` only because
  `not_found_handling = "404-page"` is set in its `wrangler.toml`. Workers'
  default for a missing asset is a bare `404` with an empty body — the
  reference site itself serves that today.
- `securitysynapse` has no custom 404 page; a plain `404` there is expected
  (Netlify has been serving its own default page).
- Confirm relative Quarto asset links resolve from the doc root.

### 6. PR preview environments are lost

Netlify provides automatic per-PR preview URLs; the GitHub Actions +
Workers workflow does not (the reference workflow notes this too). This
is not a production breakage, but it is a workflow change if PR previews
were relied on.

**Mitigation:** if previews matter, add a `wrangler deploy --env=preview`
job on `pull_request` events and test against a `*.workers.dev` URL.

### 7. Stale compatibility-date / old example

Copying an old `wrangler.toml` example with a pre-static-assets
`compatibility_date` makes `wrangler deploy` reject the `[assets]`
configuration (static assets require a compatibility date of `2024-09-23`
or later). Both files written here use current dates, so this only bites if
you source older templates.

**Mitigation:** keep `compatibility_date` at or after the reference
(`2026-01-31`).

### The single most important safeguard

Nothing is live until you push. The old Netlify apps keep serving. Until
you have (a) a green CI deploy, (b) a working `*.workers.dev` URL, and
(c) a bound + verified custom domain, **do not delete the Netlify app or
its DNS records**. This keeps the migration fully reversible — rollback
is simply re-pointing DNS to Netlify.

> Use **RUNBOOK.md** for the exact `dig` / `curl` commands to verify every
> stage as you execute the handoff. The site-specific worker names and
> build commands are in the cheat sheet below.

## Related reading

- Cloudflare Workers static assets:
  https://developers.cloudflare.com/workers/static-assets/
- Custom domains (incl. `custom_domain = true` in `wrangler.toml`):
  https://developers.cloudflare.com/workers/configuration/routing/custom-domains/
- Wrangler configuration reference:
  https://developers.cloudflare.com/workers/wrangler/configuration/
- This working reference site's `wrangler.toml` and
  `.github/workflows/publish.yml` are the proof that the pattern works.
