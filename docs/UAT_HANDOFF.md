# UAT 1.0 Handoff and UAT 2.0 Launch Notes

Date: May 4, 2026

## UAT 1.0 Result

UAT 1.0 is a success. The Docker-first review stack now has a stable GM dashboard, canonical demo roster, repeatable cleanup/seed process, and SSVC coverage for the main account, roster, assignment, RBAC, password reset, and auth-stress flows.

The current branch is the base for UAT 2.0:

- Branch: `dev/ssvc-acp-cabinet`
- GM account: `117_HeadcoachGM`
- GM category tag: `117_MASTER_CHIEF`
- AGM category lanes: `001_INFINITY`, `002_REACH`, `003_FORERUNNER`, `004_ODST`
- Holding category: `XXX_UNASSIGNED`

## Current Aggregation and Categorization State

The current category model is prefix-driven and should be treated as the foundation for UAT 2.0.

- `117_` is the GM lane. `117_HeadcoachGM` is the administrative boss and can also directly coach if needed.
- `001_` through `004_` are AGM/head-coach lanes. These are team categories and own their downstream tag propagation.
- `XXX_UNASSIGNED` is the intake/holding state for active head coaches, line coaches, and athletes that are not currently attached to a GM/AGM/team.
- Normal member prefixes are `000_` and `005_` through `099_`. Reserved org prefixes `001_`, `002_`, `003_`, `004_`, and `117_` are blocked for athlete auto-assignment and line-coach self-selection.

Current canonical demo roster:

- GM: `117_HeadcoachGM`
- Standalone head coaches: `118_Headcoachtwo`, `119_Headcoachthree`, `120_Headcoachfour`, `121_Headcoachone`
- Line coaches: `008_Coachone`, `013_Coachtwo`, `048_Coachthree`, `088_Coachtfour`
- Assigned primary athlete: `000_Athlete1`
- Unassigned athlete pool: `005_Athlete2` through `021_Athlete16`, skipping `008_` and `013_` because line coaches own those prefixes

Tag propagation currently works as follows:

- An athlete assigned to a line coach inherits the line coach's accountable head-coach org tag.
- An athlete assigned directly to a head coach inherits that head coach's org tag.
- A line coach assigned to an AGM inherits that AGM lane.
- A line coach assigned to GM inherits `117_MASTER_CHIEF`.
- Active users without an accountable parent display as `XXX_UNASSIGNED`.

## UAT 1.0 Key Features Added

- GM filing-cabinet dashboard for `117`, `001`, `002`, `003`, and `004` category lanes.
- Protected empty template pages for non-GM category tabs.
- GM management of standalone head coaches:
  - Assign/reassign into `001-004`
  - Move back to `XXX_UNASSIGNED`
  - Soft-delete with recovery metadata
- Line-coach roster table aligned with the athlete table pattern.
- Athlete roster supports reassign/delete and responsive mobile rendering.
- `XXX_UNASSIGNED` is available as a first-class category option.
- 15 seeded unassigned athletes exist for manual assignment UAT.
- Public athlete registration auto-assigns the next available valid normal prefix.
- Coach registration rejects reserved and out-of-pool prefixes.
- Demo cleanup is repeatable and preserves the canonical roster.
- Docker SSVC validates API UAT, auth stress, cleanup before/after UAT, and frontend/backend reachability.

## Major Bugs and Fixes To Remember

- Problem: GM could not see or manage unassigned/outside athletes and coaches.
  - Fix: Expanded head roster APIs so GM dashboard can see active staff and athletes needed for onboarding/reassignment.

- Problem: Athlete and line-coach action alignment broke on desktop and mobile.
  - Fix: Refactored line coaches into the same table structure as athletes and centered mobile table cards consistently.

- Problem: Cleanup/seed could crash with duplicate email conflicts after UAT temporarily renamed head coaches into AGM lanes.
  - Fix: Added canonical rename/archive logic and email release before refreshing canonical demo users.

- Problem: `XXX_UNASSIGNED` was only a display fallback, not an actionable dropdown option.
  - Fix: Added explicit frontend option and backend support to move AGM head coaches back to standalone unassigned identities.

- Problem: `117_Headcoachone` and `121_Headcoachfive` naming no longer matched the intended GM/AGM flow.
  - Fix: Renamed GM to `117_HeadcoachGM`, changed the assignable standalone source to `121_Headcoachone`, and added legacy migration aliases for old rows.

- Problem: Provisioning validation assumed all line coaches must report directly to GM.
  - Fix: Updated validation to accept line coaches assigned to either `117_HeadcoachGM` or an active AGM head coach in `001-004`.

## UAT 2.0 Direction

UAT 2.0 should focus on loosening GM restrictions while keeping AGM and line-coach RBAC strict.

GM expectations:

- GM can manage many head coaches, many line coaches, and many athletes.
- GM can accept zero of any downstream type.
- GM can directly coach athletes if needed.
- GM should not hit normal org-boundary walls in dashboard assignment, reassignment, delete, or recovery flows.

AGM/head-coach expectations:

- An AGM has at most one GM.
- An AGM can manage many line coaches and many athletes inside only their team.
- AGM views should see no more and no less than their own downstream team data.
- AGM can be demoted to line coach.

Line-coach expectations:

- A line coach can report to either one GM or one AGM, or be temporarily unassigned.
- A line coach can manage many athletes.
- A line coach can be promoted to AGM/head coach.

Athlete expectations:

- An athlete can have zero or one accountable coach at a time.
- A valid accountable coach can be GM, AGM/head coach, or line coach.
- Athlete reassignment should offer the exhaustive valid target list for GM: `XXX_UNASSIGNED`, GM, active AGM/head coaches, and active line coaches.

## UAT 2.0 RBAC Work Items

- Add an explicit GM bypass in head-dashboard APIs for active non-staff user management.
- Keep AGM scoping strict: only their team data, assignments, programs, and analytics.
- Keep line-coach scoping strict: only their athletes/programs.
- Update athlete reassignment dropdown to include all valid targets for GM.
- Add tests for GM assigning athletes directly to:
  - GM
  - AGM head coach
  - line coach under GM
  - line coach under AGM
  - `XXX_UNASSIGNED`
- Add tests that AGM cannot access another AGM lane.
- Add tests for promotion/demotion flows:
  - Line coach to AGM
  - AGM to line coach
  - old normal prefix is released when promoted to AGM

## Future Skill Tracking Tags

Investigate a skill tracking/tagging layer that can be applied within each team lane:

- `NOBLE`: Advanced to Pro
- `RED`: Moderate to Advanced
- `SILVER`: Novice to Moderate
- `BLUE`: Rookie to Novice

This should help with finer-grained aggregation and programming decisions. The long-term goal is for each athlete to carry both:

- Team/org tag: `117`, `001`, `002`, `003`, or `004`
- Skill tag: `NOBLE`, `RED`, `SILVER`, or `BLUE`

This enables dashboards to compare:

- Athlete vs own skill group inside the same team
- Athlete vs full team
- Team skill group vs same skill group across all teams
- Team aggregate vs whole organization

This is high-value for future analytics and program recommendation work.

## UAT 3.0 Nice-To-Have: Local Domain

Preserve this as a future polish item, not a UAT 2.0 blocker.

For local demos, the current Docker frontend can be reached with a friendlier hostname by adding this to `/etc/hosts`:

```txt
127.0.0.1  115-weightlifting.local
```

Then open:

```txt
http://115-weightlifting.local:4173/head
```

Later, a reverse proxy could remove the `:4173` port and provide a cleaner URL. That would be a UAT 3.0-level polish task because it likely touches Docker Compose, frontend origin config, backend allowed hosts/origins, and documentation.

## UAT 3.0 MVP Direction

UAT 3.0 starts the role-specific UX shell:

- GMHC: god-tier organization dashboard, full roster metrics, compliance visibility, schedule ownership, and settings foundation.
- AGMHC: assigned-team dashboard only, with access to assigned line coaches and athletes.
- LC: assigned-athlete programming and management only.
- Settings priority 1: account profile, protected username prefix messaging, email/phone, athlete card demographics, privacy note, role-aware controls, and coach certification tracking.
- Schedule priority 2: spreadsheet-first coach coverage view with daily, weekly, and monthly outlook placeholders.
- Simple/Complex priority 3: persisted UX mode toggle so the interface can reduce visual density for users who want a quieter workflow.

UAT 4.0 idea capture lives in `docs/UAT_4_ROLLING_NOTES.md`.

## Pre-Sleep Validation Checklist

Before ending this UAT 1.0 phase, run:

- Lints on edited files
- Focused account tests
- Full Docker SSVC
- Direct DB sanity check for canonical head roster and unassigned athlete pool
- ACP to `dev/ssvc-acp-cabinet`
