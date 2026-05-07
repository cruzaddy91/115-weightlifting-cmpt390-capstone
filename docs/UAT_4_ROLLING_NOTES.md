# UAT 4.0 Rolling Notes

Date started: May 5, 2026

This is a living idea file for post-UAT 3.0 work. Keep MVP UAT 3.0 focused on role-aware dashboard shell, settings foundation, schedule foundation, and simple/complex UX.

## How To Use

Create a "How to Use" page with screenshots or PDF downloads. The first artifact to preserve is:

- Source PDF: `/Users/addycruz/Desktop/115 Weightlifting_GM_HEAD_MAIN_DASH.pdf`
- Page key: `_GM_HEAD_MAIN_DASH`

Use sequential callouts over or below each screenshot/PDF section so users can learn the dashboard in the order they would naturally use it.

## Page Naming

Dashboard and guide assets should use explicit role/page names:

- `_GM_HEAD_MAIN_DASH`
- `_AGMHC_MAIN_DASH`
- `_LC_MAIN_DASH`
- `_GMHC_PROGRAMMING_DASH`
- `_AGMHC_PROGRAMMING_DASH`
- `_LC_PROGRAMMING_DASH`
- `_ATHL_MAIN_DASH`

Add more page keys as the app grows, but keep role prefix plus purpose visible in the file/page name.

## Demo Mode

Consider a demo mode under Settings for GMHC, AGMHC, and LC accounts.

Expected behavior:

- Spin up an isolated temporary sandbox state.
- Let coaches make mistakes without touching production data.
- Warn clearly that all input data will be lost.
- Use demo mode to reduce onboarding friction for high-control dashboards.

## Continuing Education

Add a Continuing Education tab or bottom-page section for coach roles.

GMHC container:

- Mandatory trainings and required CE material.
- Compliance reminders.
- Organization-wide resource links.

Coach-submitted container:

- Coaches can submit useful links/resources.
- Submissions enter an approval queue.
- GMHC can approve.
- AGMHC can approve only if GMHC delegates that permission.

## Delegated AGMHC Controls

Default AGMHC access should remain strict. GMHC may later delegate specific controls:

- Approve Continuing Education board posts.
- Edit or manage schedule.
- Cover shift/change management.
- Additional permissions as role needs become clear.

## Multi-Lane AGMHC Assignment

The current UAT 3.0 category model is prefix-based: one active AGMHC identity maps naturally to one lane such as `001_`, `002_`, `003_`, or `004_`.

Future model work can allow one AGMHC to manage multiple lanes, for example:

- AGMHC 1 manages `001` and `002`.
- AGMHC 2 manages `003` and `004`.
- GMHC keeps god-tier access to every lane.

This likely needs an explicit category-assignment table instead of username prefix alone, plus limits such as no more than three active lane assignments per AGMHC.

## Schedule Expansion

UAT 3.0 schedule starts simple. UAT 4.0 can add:

- Shift coverage requests.
- Schedule-change approval workflow.
- Annual calendar export.
- Weekend and holiday handling.
- Read-only views for most roles, editable views for GMHC and delegated AGMHCs.

## Numbering System UAT

Use line-coach prefixes as coverage examples for coach-selected numbers and athlete auto-assignment availability:

- `008_Coachone`
- `013_Coachtwo`

These should help validate that athlete auto-assignment skips unavailable normal-member prefixes and that coach username selection respects available numbers.

## Possible Point Of Sale

Possible future POS connection. This needs careful regulatory, privacy, tax, and payment-processing review before implementation.

---

## Capture log (May 5, 2026, pre-exam pause)

**UAT 3.0 close metrics and SSVC/ACP process** are summarized in `docs/UAT_3_SSV_ACP_CLOSE_AND_UAT4_KICKOFF.md` (artifact paths, `ssvc_metrics` fields, green bar, rebuild reminders).

**Already implemented for numbering / registration (carry into UAT 4 planning only if extending):**

- Athlete self-serve: smallest free prefix in `000_` or `005_`–`099_`; coaches choose `NNN_Handle` with server validation and optional **available-prefix** fetch from `GET /api/auth/register/coach-prefixes/`.
- Docker UAT uses canonical **`Athlete17`–`Athlete35`** stress names; prune removes that numeric pattern on permanent clean.

**UAT 4.0 candidates sparked by numbering work (optional):**

- Head or admin UI surfacing **live prefix availability** (not only login form).
- Audit log when coaches change handles (if ever allowed) or when head staff renames users.
- E2E test in CI mirroring `docker_uat.py` bundle + roster checks if GitHub Actions gets a compose job.
