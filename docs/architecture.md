# Jeopardy Study

Jeopardy Study is a self-hosted, local-first study application. The backend owns clue records, session selection, attempt records, grading decisions, and dashboard calculations. React calls the Django API; the browser stores no authoritative progress.

The repository includes a small synthetic clue fixture for development. It does not include a real clue collection. Only import material you are authorized to use, and keep private source files outside version control.

## Setup and sample

Use Python 3.14 (`.python-version`) and Node 24 (`.nvmrc`). Install with `make install`, then `make setup`, then `make sample`. Local settings default to SQLite; Valkey provides the Redis-backed WebSocket and task services. Start Valkey with `make services`, then run Django and Vite with `make dev` or `make dev-backend` and `make dev-frontend`. Postgres is optional for local study.

Run the mobile browser checks with `cd frontend && pnpm exec playwright install chromium && pnpm e2e`.

## Interface design

The UI borrows the game's look without using its logo. Practice is a board-blue clue screen with uppercase serif clue text, a condensed category label, the clue value in gold (difficulty row × $200) and red countdown lights for timed rounds. Progress views are quiet: a subject range plot (subtopic rows also list proficiency by clue value) (dot = estimate, line = likely range, dashed gold rule = overall estimate) and a clue-value strip. Results show a dollar total computed in the browser for display only; attempts and grading decisions stay the source of truth.

Fonts come from the stacks in `frontend/src/style.css` (`--font-clue`, `--font-category`): a locally installed ITC Korinna or Oswald is used when present, otherwise the system serif and condensed sans. No font files are bundled, so the app ships no licensed typeface.

## Importing clue files

Import a local TSV, CSV, or JSON file with:

```sh
uv run python backend/manage.py import_clues /path/to/clues.tsv --revision source-v1
```

The importer accepts common field names: `clue_text`, `clue`, or `answer` for the clue; `correct_response`, `response`, or `question` for the response; and `original_category` or `category` for the on-air category. Optional fields include `source_url`, `id`, `show_number`, `air_date`, `round`, `clue_value`, `daily_double_value`, and `comments`. It preserves each original row as provenance and only stores a source URL when the input provides one. Use a stable revision label to make imports reproducible.

Quote normalization changes practice-facing text while preserving the original payload. Source IDs use a provided identifier when present; otherwise they derive from the import revision, show number, air date, and row number.

## Classification

Classification is optional. All practice modes that do not request subject filters can run against unclassified clues. Run `seed_taxonomy`, configure `CLASSIFICATION_MODEL` and `OPENAI_API_KEY`, and start a resumable batch with `classify_clues --limit 100 --concurrency 2` only when you want semantic filtering and dashboards. Use `classify_clues --clue-id <uuid> --reprocess` or the classification admin action to reclassify selected clues. Category labels do not constrain classification; the clue and correct response are the primary inputs.

For a local batch through the Codex CLI, run `uv run python backend/manage.py classify_clues_codex --dry-run` and then `uv run python backend/manage.py classify_clues_codex --limit 200 --max-usage-tokens 50000`. Omit `--limit` to process every pending clue; saved classifications are skipped on the next run. This uses the machine's Codex CLI login, defaults to `gpt-6-luna` with low reasoning effort, and does not read the project's `OPENAI_API_KEY`. The optional per-run token budget sums the CLI's reported input and output tokens and is checked between batches, so the final batch can take the total over the requested limit. The cap resets on each command invocation; it is a token-count stop condition, not a Codex account-credit limit. Lower `--batch-size` to reduce the possible overshoot.

## Practice flow

Untimed General Practice, Weak Areas, and Review Mistakes use reveal-first recall: think of the response, reveal it, then choose Confident, Guessed, or Didn't know. Enter reveals the response; keys 1, 2, and 3 choose a rating and advance. These ratings are stored separately and map to correct, partial, and incorrect for proficiency summaries. Anytime Test Prep remains timed and accepts typed answers, with feedback withheld until results.

## Data, backup, and limitations

Attempts and grading decisions are retained as the source for recalculating results. An attempt row is created when a clue is displayed, so normal practice avoids clues already seen even if they were skipped; proficiency counts only answered first exposures. Classification metadata is versioned separately. To back up only study progress and presets, run `make export-progress FILE=progress.json`; restore it into a database with the matching clue collection using `make import-progress FILE=progress.json`. The export stores clue fingerprints, not clue text, so a session is skipped if any of its clues are missing from the destination. Keep the export private because it contains typed responses and study history. For a complete backup, use `pg_dump --format=custom` with Postgres or stop the server and copy `backend/db.sqlite3` for SQLite. Back up `.env` secrets separately and securely. Restore a database dump with `pg_restore` or by restoring the SQLite file, then run migrations.

Difficulty is a board-row proxy inferred from round, original amount, and era; it does not measure individual clue difficulty. Anytime mode is an approximation, and its default distribution is not asserted to match the official test. The synthetic sample is too small for representative test readiness or robust proficiency claims. The first MVP does not support multi-user profiles, browser offline sync, empirical difficulty calibration, or advanced spelling adjudication.

## TSIDP deployment

Set `DJANGO_SETTINGS_MODULE=config.settings.prod`, `SECRET_KEY`, `TSIDP_ISSUER`, `TSIDP_CLIENT_ID`, `TSIDP_CLIENT_SECRET`, and `ALLOWED_IDENTITY`. Register the callback URI `/oidc/callback/` with your identity provider and use its OIDC discovery document. The configured identity must match the email, username, or subject claim. Only `/api/health` is public for Kubernetes probes; other API routes require authentication. Local mode permits a single local learner without authentication. `local_tsidp` enables local OIDC testing when credentials are present.

## CI image publishing

CircleCI runs the checks on every branch and publishes the application image to Docker Hub after they pass on `main`. Create the `dockerhub-publish` CircleCI context with `DOCKERHUB_USER`, `DOCKERHUB_PASSWORD` (a Docker Hub access token), and `DOCKERHUB_REPOSITORY` (`namespace/repository`). CI pushes an immutable `sha-<commit>-<build-number>` tag; it does not deploy to Argo CD. Kargo can observe the image and Git commit to create new freights.

## Helm release

The chart runs PostgreSQL and Valkey with persistent volume claims, and consumes a native Kubernetes Secret for application and database credentials. Its defaults use a `ClusterIP` Service and placeholder host and identity-provider values. Set deployment-specific values in an ignored local values file, including an appropriate Service type and port for your cluster. For private access, configure your own ingress or reverse proxy and its access policy. PostgreSQL pool settings belong under Django's `OPTIONS.pool`; putting them beside the pool option passes them to psycopg as invalid connection parameters. The image defaults to `jeopardy-study:local`; importing that image into a local cluster is separate from building it with Docker. The Redis stream scaler watches Valkey database 2, matching Taskiq, and can be enabled when the KEDA CRD is installed.
