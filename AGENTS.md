# Agent guidance

These instructions apply to any coding agent working in this repository. Keep tool-specific setup in the relevant tool's small entry-point file and keep shared project guidance here.

## Project conventions

- Use async-native Django request paths. `select_related` every relation an async path touches, and use `sync_to_async` only at a real sync boundary.
- Keep each controlled value in one enum under its Django app's `enums.py`; expose API enums in schemas so generated frontend types share the contract.
- Use Python 3.14's PEP 758 form for multiple exceptions: `except ValueError, TypeError:`.
- Add a database `CheckConstraint` for every Django choices field. Give migrations descriptive names that explain the behavior they change.
- Build list endpoints from batched maps; never issue one query per returned row.
- After a mutation, invalidate every client query that reads the data it changed.
- Keep comments to two lines or fewer and explain why the code needs to work that way.
- Update the relevant documentation in the same change as behavior.
- Keep source clue fields distinct from metadata added by this application.
- Treat attempts and grading decisions as the source of truth for recomputable proficiency.

## Project overview

Jeopardy Study is a self-hosted, local-first study application. The backend owns clue records, session selection, attempt records, grading decisions, and dashboard calculations. React calls the Django API; the browser stores no authoritative progress.

The repository includes a small synthetic clue fixture for development. It does not include a real clue collection. Only import material you are authorized to use, and keep private source files outside version control.

## Database environments and target selection

This project has separate local and Kubernetes application environments. They do not share database state automatically. A local K3s cluster, if used, and an Argo-managed cluster are also separate targets even if they use the same namespace or deployment names.

| Environment | Application/database | Typical use |
| --- | --- | --- |
| Local checkout | Django `config.settings.local`; SQLite at `backend/db.sqlite3` by default | Development, local clue classification, and local tests or scripts |
| Kubernetes | Django production settings in the API pod; PostgreSQL PVC in namespace `jeopardy` | The hosted practice application and its persistent clues, classifications, sessions, and progress |

Local settings read `.env`. A `DATABASE_URL` exported in the shell or set in `.env` overrides the default SQLite path. Therefore, do not infer the target from the command name, working directory, or the fact that a command runs on this machine. Before any database read that informs a decision or any database write, identify the active database using only non-secret fields. Never print or paste `DATABASE_URL`, database passwords, or the full Django database settings.

Check the local command's configured target with:

```sh
uv run python backend/manage.py shell -c \
  'from django.conf import settings; d = settings.DATABASES["default"]; print(d["ENGINE"], d.get("NAME"), d.get("HOST"))'
```

The result should say `django.db.backends.sqlite3` and point to this checkout's `backend/db.sqlite3` when you intend to use the default local database. If the engine or path differs, stop and establish which data the URL targets before proceeding.

The Kubernetes API and its management commands use the database configured inside the pod. Before a hosted read or write, check `kubectl config current-context` and confirm the namespace and deployment; the context determines which cluster receives the command. The usual release uses namespace `jeopardy`, deployment `jeopardy-api`, and container `api`. To inspect the pod's database target without exposing credentials:

```sh
kubectl exec -n jeopardy deploy/jeopardy-api -c api -- \
  python manage.py shell -c \
  'from django.conf import settings; d = settings.DATABASES["default"]; print(d["ENGINE"], d.get("NAME"), d.get("HOST"))'
```

Running a local Django command does not update the hosted app. Argo CD sync deploys Kubernetes manifests and images; it does not copy clue or classification rows between databases. If a task concerns hosted practice, verify results in the Kubernetes database after the write.

### Classification workflow

The Codex CLI classifier runs on the local machine and classifies whichever database local Django settings resolve to. For the default local-first workflow, keep it on the local SQLite database, then explicitly import its saved classifications to Kubernetes:

```sh
uv run python backend/manage.py classify_clues_codex --dry-run
uv run python backend/manage.py classify_clues_codex --limit 200 --max-usage-tokens 50000
scripts/import_local_codex_results_to_k8s.sh
```

For a resumable run over all pending local clues that imports saved results afterward, use `scripts/classify_and_import_local_codex.sh`. `scripts/run_codex_classification_until_stalled.sh` only classifies the currently configured local database; it does not import to Kubernetes.

The importer runs inside the API pod, so it uses the cluster's PostgreSQL connection and Kubernetes Secret. It matches records by source ID and content fingerprint, maps taxonomy by stable slugs, preserves hosted classifications that already exist, and skips local-only clues. Seed the same taxonomy in the cluster before importing if it is missing:

```sh
kubectl exec -n jeopardy deploy/jeopardy-api -c api -- python manage.py seed_taxonomy
```

Confirm `kubectl` context, namespace, and target deployment before any import. A local `.env` is ignored by Git and may contain local development settings; this transfer workflow does not need Kubernetes database credentials in that file. Keep Kubernetes secrets in the cluster's Secret resources and do not commit secrets or private clue data.

The optional `--max-usage-tokens` limit sums the Codex CLI's reported input and output tokens and is checked between batches, so the final batch can take the total over the requested limit. The cap resets for each command invocation; it is a token-count stop condition, not an account-credit limit. Lower `--batch-size` to reduce the possible overshoot.

## Development setup

Use Python 3.14 (`.python-version`) and Node 24 (`.nvmrc`). Install with `make install`, then `make setup`, then `make sample`. Local settings default to SQLite; Valkey provides the Redis-backed WebSocket and task services. Start Valkey with `make services`, then run Django and Vite with `make dev` or `make dev-backend` and `make dev-frontend`. Postgres is optional for local study. Run `make hooks` to install Lefthook pre-commit hooks (needs the `lefthook` binary) that run the cheap CI lint jobs (ruff, mypy, oxlint, tsc, helm lint) on relevant staged changes; `git commit --no-verify` bypasses them.

Run the mobile browser checks with `cd frontend && pnpm exec playwright install chromium && pnpm e2e`.

## Interface design

The UI borrows the game's look without using its logo. Practice is a board-blue clue screen with uppercase serif clue text, a condensed category label, the clue value in gold (difficulty row × $200) and red countdown lights for timed rounds. Progress views are quiet: a subject range plot (dot = estimate, line = likely range, dashed gold rule = overall estimate), with subtopic rows listing proficiency by clue value, and a clue-value strip. Results show a dollar total computed in the browser for display only; attempts and grading decisions stay the source of truth.

Controls (buttons, cards, inputs, selects, sliders, switches, dialogs, toasts) are shadcn/ui components in `frontend/src/components/ui`, themed through the CSS variables at the top of `frontend/src/style.css`; add more with `pnpm dlx shadcn@latest add <name>` from `frontend/`. The clue board and range plots keep their hand-written styles.

Fonts come from the stacks in `frontend/src/style.css` (`--font-clue`, `--font-category`): a locally installed ITC Korinna or Oswald is used when present, otherwise the system serif and condensed sans. No font files are bundled, so the app ships no licensed typeface.

## Importing clue files

Import a local TSV, CSV, or JSON file with:

```sh
uv run python backend/manage.py import_clues /path/to/clues.tsv --revision source-v1
```

The importer accepts common field names: `clue_text`, `clue`, or `answer` for the clue; `correct_response`, `response`, or `question` for the response; and `original_category` or `category` for the on-air category. Optional fields include `source_url`, `id`, `show_number`, `air_date`, `round`, `clue_value`, `daily_double_value`, and `comments`. It preserves each original row as provenance and only stores a source URL when the input provides one. Use a stable revision label to make imports reproducible.

Quote normalization changes practice-facing text while preserving the original payload. Source IDs use a provided identifier when present; otherwise they derive from the import revision, show number, air date, and row number.

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

See [the architecture and environment guide](docs/architecture.md) and [the Helm operations guide](helm/jeopardy/README.md) for deployment-specific details.
