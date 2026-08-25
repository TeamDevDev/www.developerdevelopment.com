# Developer Development

This repository contains the source for the [Developer Development](https://developerdevelopment.com/) website. The site provides course materials for undergraduate software engineering, including content from:

- [Software Engineering at Google](https://abseil.io/resources/swe-book)
- [The Fuzzing Book](https://www.fuzzingbook.org/)
- [The Debugging Book](https://www.debuggingbook.org/)

The website is built with [Quarto](https://quarto.org/) and deployed as a
static-asset [Cloudflare Worker](https://developers.cloudflare.com/workers/).

## Requirements

Install the following tools locally:

- [Quarto](https://quarto.org/docs/get-started/)
- [uv](https://docs.astral.sh/uv/)
- Python 3.11 (the repository pins this version in `.python-version` for
  reproducible builds)

Python dependencies are declared in `pyproject.toml`, resolved in `uv.lock`,
and installed into uv's project environment.

## Initial setup

From the repository root, synchronize the locked dependencies:

```bash
uv sync --locked
```

To update dependencies after changing `pyproject.toml`, run:

```bash
uv lock
uv sync
```

Use `uv add` when adding a dependency so that both `pyproject.toml` and
`uv.lock` remain consistent:

```bash
uv add package-name
uv add --dev development-package-name
```

## Build the website

Render the optimized website with:

```bash
uv run quarto render --profile optimize
```

The `optimize` profile runs the pre-render and post-render minification steps
defined in `_quarto-optimize.yml`. The generated site is written to `_site/`.

For a development preview, use:

```bash
quarto preview
```

The preview command intentionally does not run the complete optimization
pipeline. To serve an already-rendered site locally:

```bash
cd _site
python -m http.server 8000
```

## Continuous integration

The GitHub Actions workflows use uv exclusively for Python setup:

- `.github/workflows/build.yml` renders the site for pushes and pull requests.
- `.github/workflows/publish.yml` renders and deploys the site to Cloudflare
  Workers on pushes to `master`.

Both workflows install uv, run `uv sync --locked`, and invoke Quarto with `uv run`.

## Cloudflare migration and deployment

The migration helper automates the Cloudflare setup and deployment stages:

```bash
uv run scripts/migrate-to-cloudflare.py \
  --config scripts/migrate-configs/developerdevelopment.toml \
  --stage check
```

Run the remaining stages only after reviewing the generated configuration and
confirming the DNS changes:

```bash
uv run scripts/migrate-to-cloudflare.py \
  --config scripts/migrate-configs/developerdevelopment.toml \
  --stage all
```

Before running the migration, export `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID` in the shell. The API token must have the permissions
documented in [MIGRATE.md](MIGRATE.md). Keep the Netlify site available until
the Cloudflare deployment and verification checks pass.

For another site, create a migration TOML file with its Worker name, apex
zone, GitHub repository, and render command. The optional `hostnames` setting
controls the domains to bind and defaults to the apex plus `www`; the optional
`netlify_apex_ips` setting lists old Netlify A-record addresses and defaults to
`75.2.60.5`. The script removes only recognized Netlify records and preserves
a DNS snapshot before making changes.

See the following files for more details:

- [MIGRATE.md](MIGRATE.md) — Cloudflare migration plan and configuration
- [RUNBOOK.md](RUNBOOK.md) — migration checkpoints and verification commands
- `scripts/migrate-configs/developerdevelopment.toml` — site-specific migration
  settings
- `wrangler.toml` — Cloudflare Worker static-assets configuration

## Repository layout

```text
_quarto.yml                 Main Quarto configuration
_quarto-optimize.yml        Optimized build profile
blog/                       Course blog posts
schedule/                   Course schedule
scripts/minify-files.py     CSS, HTML, and JavaScript minification
scripts/migrate-to-cloudflare.py
                            Cloudflare migration helper
pyproject.toml              Project metadata and dependencies
uv.lock                     Locked dependency resolution
wrangler.toml               Cloudflare Worker configuration
```

## License and content

This repository contains educational course materials and supporting website
code. Refer to the individual source files and linked projects for their
applicable licenses and attribution requirements.
