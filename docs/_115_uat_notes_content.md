# 115 Weightlifting: Netlify UAT reviewer notes

**Purpose:** Credentials and feature checklist for stakeholder testing of the hosted app (Netlify frontend plus backend on Render).

**Important:** Demo logins apply only if the hosted database was provisioned with the same seeded demo data as documented in the capstone README (Docker `SEED_DEMO`-style roster). If the production or UAT database was started empty (`SEED_DEMO=false`), use the professor-specific account you configured on Render instead. That account lives only in deployment secrets and is not listed here.

---

## Demo password (seeded roster)

All seeded demo accounts use this password:

`Passw0rd!123`

(Source: CMPT390 capstone repository README, Demo Credentials section.)

---

## Suggested usernames to share first

| Role | Username |
|------|----------|
| GM head coach | `117_HeadCoachGM` |
| Line coach | `008_Coach_eight` |
| Athlete (seeded with assigned programs and dashboard data) | `000_Athlete_zero` |

**Also available in the seeded roster (same password):**

- AGM lane heads: `001_HeadCoach_one`, `002_HeadCoach_two`, `003_HeadCoach_three`, `004_HeadCoach_four`
- Additional line coaches: see README walkthrough tables (`013_Coach_onethree`, `022_Coach_twotwo`, and other handles documented there)
- Other seeded canon athletes (31 accounts with prefixes documented in the README normal-member pool)

**Coach signup code:** Self-service line-coach registration on a live deploy requires the `coach_signup_code` set in backend environment variables. If signup fails with the public form, reviewers can use the pre-seeded coach usernames above.

---

## Feature areas suitable for manual UAT

1. **Authentication**: Login per role; JWT-backed session stability; password reset if enabled (may log to backend instead of real email on UAT).

2. **Athlete dashboard**: View assigned programs, log workouts, completions, personal records where data exists.

3. **Line coach dashboard**: Create and manage programming for athletes assigned to that coach only.

4. **Head coach dashboard**: Organization summary, full roster views, assigning athletes to coaches, staff and organization hierarchy visuals.

5. **Programs**: Structured training programs tied to athletes; create and update flows.

6. **Workout logs and completion**: Athlete-side logging aligned with assigned programs.

7. **Personal records (PRs)**: Athletes and coaches within scope; RBAC should prevent one coach reading another athlete's PRs when not authorized.

8. **Sinclair-related analytics**: Head and analytics flows as exposed in the UI for the seeded environment.

9. **Charts and roster UX**: Time-series or comparison visuals; head roster skill views where present.

10. **Registration**: Athlete registration and username validation rules; optional coach registration if signup code matches the deployed backend.

---

*Generated for reviewer handoff. Demo password and roster match the professor-facing Docker capstone README when demo seed is enabled.*
