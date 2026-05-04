# CLI Cheat Sheet

Quick reference for operating the `115 Weightlifting` app from the terminal. The local app directory is `115-weightlifting/`.

## Start Here

```bash
cd /Users/addycruz/Workspace/CMPT-390_CSCapstone/115-weightlifting
./bin/zw help
```

## Ship checklist (develop → validate → commit → push)

Run in order before every push:

```bash
./bin/zw smoke-all   # API smoke, settings smoke, vitest + production build
./bin/zw test        # Django checks, migration drift check, app tests, Vitest, frontend build
```

Then commit and push from the repo root (`git status`, `git add`, `git commit`, `git push`).

## Core Project Control

```bash
./bin/zw setup
./bin/zw doctor
./bin/zw doctor --json
./bin/zw status
./bin/zw test
./bin/zw uat
./bin/zw release
./bin/zw report
```

Report outputs:

```text
var/reports/REPORT.md
var/reports/index.html
var/reports/app_snapshot.json
var/reports/UAT_REPORT.md
var/reports/uat_latest.json
var/reports/events/
```

## Local Run Modes

```bash
./bin/zw dev
./bin/zw host-local foreground
./bin/zw host-local start
./bin/zw host-local status
./bin/zw host-local stop
./bin/zw logs
```

## Demo Data

```bash
./bin/zw seed-demo
./bin/zw reset-demo
./bin/zw reset-demo --yes
./bin/zw prune-demo              # preview: keep Coachone+5 GoT and Coachtwo+5 LotR only
./bin/zw prune-demo --yes        # apply (runs backup first), refreshes canonical passwords
./bin/zw prune-demo --yes --scrub-events   # also delete var/reports/events/*.json
./bin/zw seed-coachtwo-lotr      # Coachtwo + 5 LotR + 3y PR/workout history (ORM)
./bin/zw seed-coachtwo-lotr --with-programs   # same + programs via HTTP (API up)
# API up: backfill program completion (coach % / x of y done) for both demo rosters; avoids all-0 rings
./bin/zw backfill-demo-completion
./bin/zw backfill-demo-completion --dry-run
# Same API, no new programs — fill completion for existing programs only (default coach Coachtwo)
./bin/zw backfill-coach-completion
./bin/zw backfill-coach-completion Coachone
./bin/zw make-demo
./bin/zw smoke
```

Minimal smoke users (`seed-demo` / `reset-demo`):

```text
coach_smoke   / DemoPass123!
athlete_smoke / DemoPass123!
```

Canonical sim roster after `prune-demo --yes` (password `Passw0rd!123` unless you set `DEMO_PASSWORD`):

```text
Coachone, jon_snow, daenerys_targaryen, tyrion_lannister, arya_stark, sansa_stark
Coachtwo, frodo_baggins, samwise_gamgee, merry_brandybuck, pippin_took, gandalf_grey
```

## Data Safety

```bash
./bin/zw backup
./bin/zw export-data
./bin/zw export-data var/backups/custom_export.json
./bin/zw import-data var/backups/export_YYYYMMDD_HHMMSS.json --yes
./bin/zw restore --sqlite var/backups/db_YYYYMMDD_HHMMSS.sqlite3 --yes
./bin/zw restore --fixture var/backups/data_YYYYMMDD_HHMMSS.json --yes
```

## Cleanup

Preview:

```bash
./bin/zw clean
```

Apply:

```bash
./bin/zw clean --yes
```

Deep clean including `node_modules`:

```bash
./bin/zw clean --deep --yes
```

## Public Hosting Prep

```bash
./bin/zw prepare-public
```

Related files:

```text
config/self_hosting.md
config/self_hosting/Caddyfile.example
config/self_hosting/backend.env.production.example
config/self_hosting/frontend.env.production.example
config/self_hosting/weightlifting-backend.service
```

## Practical Sequences

### Fresh machine

```bash
./bin/zw setup
./bin/zw doctor
./bin/zw make-demo
./bin/zw host-local foreground
```

### Before a demo

```bash
./bin/zw doctor
./bin/zw reset-demo --yes
./bin/zw make-demo
./bin/zw smoke
./bin/zw host-local foreground
```

### Before deployment work

```bash
./bin/zw backup
./bin/zw test
./bin/zw release
./bin/zw prepare-public
```
