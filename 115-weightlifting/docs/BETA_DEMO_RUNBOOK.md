# 115 Weightlifting Beta Demo Script (Practice Now)

## 4-Minute Version (use this if time is tight)

### 0:00-0:15 Opening
"Hi Professor, this beta demo proves three things quickly: secure role-based login, coach program assignment workflow, and real backend API persistence."

### 0:15-0:25 What I will prove
"I’ll show auth works, coach create/assign works, and then API evidence in Network."

### 0:25-1:00 Login + role gate
- Go to `/login`
- Sign in with coach account
- Land on coach dashboard

Say:
"Login routes by role after token authentication and current-user resolution."

### 1:00-2:30 Coach flow: create + assign
- In **Create Program**:
  - Enter name
  - Select athlete
  - Set dates
  - Add one day + one exercise
  - Click **Create Program**
- If needed, use assign/reassign control once

Say:
"This flow sends a structured payload from React to DRF validation and database persistence."

### 2:30-3:30 API proof
- Open DevTools -> Network
- Trigger one small program action (update/reassign)
- Click request and show:
  - endpoint URL
  - status code
  - response payload

Say:
"This confirms the same UI action is persisted through backend API, not local-only state."

### 3:30-4:00 Close
"Recap: role-based auth passed, coach create/assign passed, and backend API persistence is visible. Current limitation is production auth/session hardening. Next step is implementing those hardening updates while preserving this workflow."

---

## 20-Second Backup Script (if demo hiccups)
"I’m seeing a live environment hiccup, so I’ll switch to validated evidence from this same build. Here are successful API traces showing auth and program endpoints passing, which confirms the implemented backend flow."

---

## Ultra-Fast Checklist Before You Start
- App is running and reachable
- Coach login credentials ready
- Athlete exists in dropdown
- DevTools Network open (Preserve log on)
- One backup screenshot/report ready
- Timer visible
