# 115 Weightlifting Beta Demo Runbook (4 Minutes)

## Goal

Prove three checkpoints fast:

1. Auth + role-gated access works.
2. Coach can create and assign a program.
3. Backend API persistence is real and visible.

## 4-Minute Timeline

- **0:00-0:15** Opening
- **0:15-0:25** State proof checkpoints
- **0:25-1:00** Login as coach + role gate
- **1:00-2:30** Create + assign program
- **2:30-3:30** Show API evidence (Network)
- **3:30-4:00** Recap, limitation, next step

---

## Script + Click Cues

### 0:00-0:15 Opening

**Say:**
- "This demo validates three graded outcomes in four minutes: secure coach access, end-to-end program assignment, and verified backend persistence."
- "I will show both UX proof and technical proof so you can see not just what works, but how it is wired."

### 0:15-0:25 Checkpoints

**Say:**
- "Checkpoint one is authentication and role-based routing."
- "Checkpoint two is coach create-and-assign workflow."
- "Checkpoint three is direct API/network evidence of persistence."

### 0:25-1:00 Login + Role Gate

**Do:**

1. Open `/login`.
2. Enter coach credentials.
3. Click **Log in**.
4. Confirm coach dashboard view.

**Say:**
- "Auth uses token-based login; the frontend stores the token and requests current user context."
- "Role-gated routing then sends this account to the coach dashboard, not athlete-only views."
- "If asked about configuration: this path depends on backend auth settings, allowed origins, and correct API base URL in frontend env."

### 1:00-2:30 Coach Create + Assign

**Do:**

1. In **Create Program**, enter program name + dates.
2. Pick athlete from dropdown.
3. Add one day and one exercise.
4. Click **Create Program**.
5. If assignment control is separate, assign/reassign once.

**Say:**
- "The form emits a normalized payload for program metadata, athlete reference, and exercise blocks."
- "Backend DRF serializers validate schema/types before saving to relational tables."
- "This proves the frontend form contract matches backend API expectations and model constraints."
- "If asked about stack boundaries: React UI -> REST endpoint -> Django/DRF serializer -> database write."

### 2:30-3:30 API Evidence

**Do (preferred):**

1. Open DevTools -> Network.
2. Trigger small update/reassign action.
3. Show endpoint path, status code, and response payload.

**Say:**
- "The network trace shows the exact endpoint, method, and status code for the action we triggered."
- "Response payload includes IDs/timestamps, which indicates server-side commit rather than local-only UI state."
- "This gives grading evidence for API correctness, data contract validity, and persistence behavior."

### 3:30-4:00 Close

**Say:**
- "Recap: role-based auth passed, coach create/assign passed, and backend persistence is visible in API traces."
- "Known limitation: production hardening is not complete yet (session/auth security controls and deployment polish)."
- "Next step: finalize security hardening and deployment configuration for stable beta rollout."

---

## 20-Second Recovery Script

"There is a live environment hiccup, so I’ll switch to validated artifact evidence from this same build. Here are successful API traces for auth and program endpoints, confirming the implemented flow still passes."

---

## Pre-Demo Fast Checklist (2 minutes)

- App stack running and reachable.
- Coach account works.
- At least one athlete exists.
- Network tab open with preserve log.
- One backup API evidence artifact open.
- Timer visible.

