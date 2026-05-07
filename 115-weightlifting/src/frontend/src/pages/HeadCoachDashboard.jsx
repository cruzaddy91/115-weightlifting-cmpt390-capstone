import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  deleteHeadAthlete,
  deleteHeadCoach,
  deleteHeadStaff,
  getHeadProgramNameOutcomes,
  getHeadModelStatus,
  getHeadOrgRoster,
  getHeadOrgSummary,
  getHeadProgramStyleOutcomes,
  getHeadRecommendations,
  patchHeadAthletePrimaryCoach,
  patchHeadAthleteSkillTeam,
  patchHeadCoachCategory,
  patchHeadStaffAssignment,
  postHeadStaffInvite,
} from '../services/api'
import { getCurrentUser } from '../utils/auth'
import { formatApiError } from '../utils/errors'
import './HeadCoachDashboard.css'

/** Skill-team athlete tables use `head-skill-roster-table` only (never `head-athlete-table`) so mobile
 *  stacked-card CSS does not flatten rows / grid-squeeze selects. After changing this file or CSS, rebuild
 *  the frontend image: from repo root, `docker compose build frontend --no-cache` (preview bakes `dist` at build).
 */
const COACH_ACCENT_CLASSES = [
  'olive-drab',
  'od-green',
  'steel-blue',
  'slate-gray',
  'burnt-umber',
  'brass',
  'muted-crimson',
  'desert-brown',
  'dark-teal',
  'graphite',
]
const SHOW_HEAD_ANALYTICS = false
/** Optional skeleton standalone heads (`118_`…`121_` style); default demo/pkg_large roster has none. */
const EXPECTED_STANDALONE_HEAD_SUFFIXES = []
const EXPECTED_AGM_HEAD_COACHES = [
  '001_HeadCoach_one',
  '002_HeadCoach_two',
  '003_HeadCoach_three',
  '004_HeadCoach_four',
]
const EXPECTED_LINE_COACHES = [
  '008_Coach_eight',
  '013_Coach_onethree',
  '048_Coach_foureight',
  '088_Coach_eighteight',
  '022_Coach_twotwo',
  '023_Coach_twothree',
  '024_Coach_twofour',
  '025_Coach_twofive',
]
const EXPECTED_PRIMARY_ATHLETE = '000_Athlete_zero'
const EXPECTED_PRIMARY_COACH = '008_Coach_eight'
const EXPECTED_UNASSIGNED_ATHLETES = [
  '005_Athlete_five',
  '006_Athlete_six',
  '007_Athlete_seven',
  '009_Athlete_nine',
  '010_Athlete_onezero',
  '011_Athlete_oneone',
  '012_Athlete_onetwo',
  '014_Athlete_onefour',
  '015_Athlete_onefive',
  '016_Athlete_onesix',
  '017_Athlete_oneseven',
  '018_Athlete_oneeight',
  '019_Athlete_onenine',
  '020_Athlete_twozero',
  '021_Athlete_twoone',
  '026_Athlete_twosix',
  '027_Athlete_twoseven',
  '028_Athlete_twoeight',
  '029_Athlete_twonine',
  '030_Athlete_threezero',
  '031_Athlete_threeone',
  '032_Athlete_threetwo',
  '033_Athlete_threethree',
  '034_Athlete_threefour',
  '035_Athlete_threefive',
  '036_Athlete_threesix',
  '037_Athlete_threeseven',
  '038_Athlete_threeeight',
  '039_Athlete_threenine',
  '040_Athlete_fourzero',
  '041_Athlete_fourone',
]
const AGM_CATEGORY_OPTIONS = [
  { prefix: 'XXX_UNASSIGNED', label: 'XXX_UNASSIGNED' },
  { prefix: '001', label: '001_INFINITY' },
  { prefix: '002', label: '002_REACH' },
  { prefix: '003', label: '003_FORERUNNER' },
  { prefix: '004', label: '004_ODST' },
]
const HEAD_CATEGORY_LINKS = [
  {
    prefix: '117',
    label: '117_MASTER_CHIEF',
    username: '117_HeadCoachGM',
    status: 'Global admin: the boss',
    colorKey: 'sage-green',
    to: '/head',
  },
  {
    prefix: '001',
    label: '001_INFINITY',
    username: 'UNASSIGNED',
    status: 'Empty assistant-manager template',
    colorKey: 'gun-silver',
    to: '/head/categories/001',
  },
  {
    prefix: '002',
    label: '002_REACH',
    username: 'UNASSIGNED',
    status: 'Empty assistant-manager template',
    colorKey: 'shell-copper',
    to: '/head/categories/002',
  },
  {
    prefix: '003',
    label: '003_FORERUNNER',
    username: 'UNASSIGNED',
    status: 'Empty assistant-manager template',
    colorKey: 'sand-tan',
    to: '/head/categories/003',
  },
  {
    prefix: '004',
    label: '004_ODST',
    username: 'UNASSIGNED',
    status: 'Empty assistant-manager template',
    colorKey: 'steel-blue',
    to: '/head/categories/004',
  },
]
const AGM_PREFIXES = new Set(['001', '002', '003', '004'])
const SCHEDULE_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const CERTIFICATION_TYPES = ['CPR/AED', 'USAW', 'ACPT/NCCA', 'Open gym/class safety']
const SKILL_TEAM_CONFIG = [
  { key: 'NOBLE', label: 'NOBLE TEAM', tone: 'noble' },
  { key: 'RED', label: 'RED TEAM', tone: 'red' },
  { key: 'SILVER', label: 'SILVER TEAM', tone: 'silver' },
  { key: 'BLUE', label: 'BLUE TEAM', tone: 'blue' },
  { key: '', label: 'NO TEAM', tone: 'unassigned' },
]

const prefixForUsername = (username = '') => username.split('_', 1)[0] || ''

const groupAthletesBySkillTeam = (athletes = []) => SKILL_TEAM_CONFIG.map((team) => ({
  ...team,
  athletes: athletes.filter((athlete) => (athlete.skill_team || '') === team.key),
})).filter((team) => team.athletes.length > 0)

const accessMetaForUser = (user) => {
  const prefix = prefixForUsername(user?.username)
  if (prefix === '117') {
    return {
      key: 'gmhc',
      coachTab: 'GM Head Coach',
      shortLabel: 'GMHC',
      title: 'GM Head Coach command center',
      scope: 'God-tier organization access',
      description: 'Full active roster, AGMHC lanes, line coaches, athletes, compliance visibility, schedule oversight, and global settings.',
    }
  }
  if (AGM_PREFIXES.has(prefix)) {
    return {
      key: 'agmhc',
      coachTab: 'AGM Head Coach',
      shortLabel: 'AGMHC',
      title: 'AGM Head Coach team dashboard',
      scope: 'Assigned-team access',
      description: 'Only the line coaches, athletes, compliance dates, and metrics assigned to this AGMHC lane.',
    }
  }
  return {
    key: 'head',
    coachTab: 'Head Coach',
    shortLabel: 'HC',
    title: 'Head Coach dashboard',
    scope: 'Direct-report access',
    description: 'Only direct staff and athlete data attached to this head-coach account.',
  }
}

const HeadCoachDashboard = () => {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [roster, setRoster] = useState({ staff: [], headCoaches: [], athletes: [] })
  const [rosterLoading, setRosterLoading] = useState(true)
  const [rosterError, setRosterError] = useState('')
  const [activeHeadCategory, setActiveHeadCategory] = useState(() => {
    const currentPrefix = prefixForUsername(getCurrentUser()?.username)
    return AGM_PREFIXES.has(currentPrefix) ? currentPrefix : '117'
  })
  const [inviteUsername, setInviteUsername] = useState('')
  const [assignBusy, setAssignBusy] = useState(false)
  const [assignToast, setAssignToast] = useState(null)
  const [assignToastHovered, setAssignToastHovered] = useState(false)
  const [headCoachReassignId, setHeadCoachReassignId] = useState(null)
  const [headCoachTargetPrefix, setHeadCoachTargetPrefix] = useState('')
  const [staffReassignId, setStaffReassignId] = useState(null)
  const [staffTargetId, setStaffTargetId] = useState('')
  const [activeWorkspace, setActiveWorkspace] = useState('head')
  const [analytics, setAnalytics] = useState({
    styleGroups: [],
    nameGroups: [],
    recommendations: [],
    minimumSampleSize: 3,
    strategy: 'rule',
    modelVersion: null,
    generatedAt: null,
    fallbackReason: null,
    modelStatus: null,
  })
  const [analyticsError, setAnalyticsError] = useState('')

  const headUser = getCurrentUser()
  const headId = headUser?.id ?? headUser?.pk
  const headUserPrefix = prefixForUsername(headUser?.username)
  const accessMeta = useMemo(() => accessMetaForUser(headUser), [headUser])
  const isGmHeadUser = accessMeta.key === 'gmhc'
  const currentHeadRosterRow = useMemo(() => (
    roster.headCoaches.find((h) => h.id === headId || h.username === headUser?.username) || null
  ), [headId, headUser?.username, roster.headCoaches])
  const workspaceTabs = useMemo(() => [
    { key: 'head', label: accessMeta.coachTab },
    { key: 'line', label: 'Line Coach' },
    { key: 'schedule', label: 'Schedule' },
    { key: 'settings', label: 'Settings' },
  ], [accessMeta.coachTab])
  const visibleHeadCategoryLinks = useMemo(() => {
    if (isGmHeadUser) return HEAD_CATEGORY_LINKS
    const ownedLanePrefixes = currentHeadRosterRow?.owned_lane_prefixes || []
    if (ownedLanePrefixes.length > 0) {
      return HEAD_CATEGORY_LINKS.filter((category) => ownedLanePrefixes.includes(category.prefix))
    }
    if (AGM_PREFIXES.has(headUserPrefix)) {
      return HEAD_CATEGORY_LINKS.filter((category) => category.prefix === headUserPrefix)
    }
    return HEAD_CATEGORY_LINKS.filter((category) => category.prefix === '117')
  }, [currentHeadRosterRow, headUserPrefix, isGmHeadUser])
  const selectedHeadCategory = useMemo(
    () => visibleHeadCategoryLinks.find((category) => category.prefix === activeHeadCategory) || visibleHeadCategoryLinks[0] || HEAD_CATEGORY_LINKS[0],
    [activeHeadCategory, visibleHeadCategoryLinks]
  )
  const selectedCategoryRoster = useMemo(() => {
    const prefix = selectedHeadCategory.prefix
    if (prefix === '117') {
      return {
        headCoaches: roster.headCoaches,
        staff: roster.staff,
        athletes: roster.athletes,
      }
    }
    return {
      headCoaches: roster.headCoaches.filter((h) => h.org_prefix === prefix || (h.owned_lane_prefixes || []).includes(prefix)),
      staff: roster.staff.filter((s) => s.org_prefix === prefix),
      athletes: roster.athletes.filter((a) => a.org_prefix === prefix),
    }
  }, [roster.athletes, roster.headCoaches, roster.staff, selectedHeadCategory.prefix])
  const selectedCategoryLead = selectedCategoryRoster.headCoaches[0] || null
  const selectedCategoryStatus = selectedHeadCategory.prefix === '117'
    ? selectedHeadCategory.status
    : selectedCategoryLead
      ? `${selectedCategoryRoster.staff.length} line coach(es), ${selectedCategoryRoster.athletes.length} athlete(s)`
      : 'No AGMHC assigned yet'
  const allSkillTeamSections = useMemo(
    () => groupAthletesBySkillTeam(roster.athletes),
    [roster.athletes]
  )
  const selectedSkillTeamSections = useMemo(
    () => groupAthletesBySkillTeam(selectedCategoryRoster.athletes),
    [selectedCategoryRoster.athletes]
  )
  const summaryTotals = useMemo(() => {
    const totals = {
      coaches: isGmHeadUser ? roster.headCoaches.length + roster.staff.length : rows.length,
      athletes: isGmHeadUser ? roster.athletes.length : 0,
      programs: 0,
      prs: 0,
      workoutLogs: 0,
      styleGroups: SHOW_HEAD_ANALYTICS ? analytics.styleGroups.length : 0,
      recommendationCount: SHOW_HEAD_ANALYTICS ? analytics.recommendations.length : 0,
    }
    for (const row of rows) {
      if (!isGmHeadUser) totals.athletes += Number(row.athlete_count || 0)
      totals.programs += Number(row.program_count || 0)
      totals.prs += Number(row.personal_record_count || 0)
      totals.workoutLogs += Number(row.workout_log_count || 0)
    }
    return totals
  }, [isGmHeadUser, roster.athletes.length, roster.headCoaches.length, roster.staff.length, rows, analytics.styleGroups.length, analytics.recommendations.length])

  const scheduleCoachNames = useMemo(() => {
    const names = [...roster.headCoaches, ...roster.staff]
      .map((person) => person.username)
      .filter(Boolean)
    return names.length ? names : [headUser?.username || 'Coach']
  }, [headUser?.username, roster.headCoaches, roster.staff])

  const certificationRows = useMemo(() => {
    const visibleCoaches = isGmHeadUser ? [...roster.headCoaches, ...roster.staff] : roster.staff
    const coaches = visibleCoaches.length ? visibleCoaches : [headUser].filter(Boolean)
    return coaches.map((coach) => ({
      id: coach.id || coach.username,
      username: coach.username,
      role: coach.user_type === 'head_coach' ? 'Head coach' : 'Line coach',
      scope: isGmHeadUser ? 'GMHC visible' : 'Team visible',
    }))
  }, [headUser, isGmHeadUser, roster.headCoaches, roster.staff])

  const showAssignToast = useCallback((message) => {
    const lowered = message.toLowerCase()
    const isError = lowered.includes('could not') || lowered.includes('choose') || lowered.includes('blocked') || lowered.includes('required')
    setAssignToast({ message, kind: isError ? 'error' : 'success' })
    setAssignToastHovered(false)
  }, [])

  const topRecommendation = analytics.recommendations[0] || null

  const loadSummary = useCallback(() => {
    return getHeadOrgSummary()
      .then((data) => {
        setRows(data.coaches || [])
        setError('')
      })
      .catch((err) => {
        setError(formatApiError(err, 'Could not load org summary.'))
      })
  }, [])

  const loadRoster = useCallback(() => {
    return getHeadOrgRoster()
      .then((data) => {
        setRoster({
          staff: data.staff || [],
          headCoaches: data.head_coaches || [],
          athletes: data.athletes || [],
        })
        setRosterError('')
      })
      .catch((err) => {
        setRosterError(formatApiError(err, 'Could not load roster.'))
      })
  }, [])

  const loadAnalytics = () => {
    if (!SHOW_HEAD_ANALYTICS) return Promise.resolve()
    return Promise.all([
      getHeadProgramStyleOutcomes(),
      getHeadProgramNameOutcomes(),
      getHeadRecommendations(),
      getHeadModelStatus().catch(() => null),
    ])
      .then(([style, names, recommendations, modelStatus]) => {
        setAnalytics({
          styleGroups: style.groups || [],
          nameGroups: names.groups || [],
          recommendations: recommendations.recommendations || [],
          minimumSampleSize: style.minimum_sample_size || names.minimum_sample_size || recommendations.minimum_sample_size || 3,
          strategy: recommendations.strategy || 'rule',
          modelVersion: recommendations.model_version || null,
          generatedAt: recommendations.generated_at || null,
          fallbackReason: recommendations.fallback_reason || null,
          modelStatus,
        })
        setAnalyticsError('')
      })
      .catch((err) => {
        setAnalyticsError(formatApiError(err, 'Could not load analytics.'))
      })
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setRosterLoading(true)
    Promise.all([loadSummary(), loadRoster(), loadAnalytics()])
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
          setRosterLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [loadSummary, loadRoster])

  useEffect(() => {
    if (!visibleHeadCategoryLinks.some((category) => category.prefix === activeHeadCategory)) {
      setActiveHeadCategory(visibleHeadCategoryLinks[0]?.prefix || '117')
    }
  }, [activeHeadCategory, visibleHeadCategoryLinks])

  useEffect(() => {
    if (!assignToast || assignToastHovered) return undefined
    const timeout = window.setTimeout(() => {
      setAssignToast(null)
    }, 4500)
    return () => window.clearTimeout(timeout)
  }, [assignToast, assignToastHovered])

  const coachOptions = () => {
    if (!headId) return []
    const isGm = (headUser?.username || '').startsWith('117_')
    const opts = []
    const seen = new Set()
    const addOption = (id, label) => {
      if (id == null || seen.has(id)) return
      seen.add(id)
      opts.push({ id, label })
    }
    addOption(headId, `@${headUser?.username || 'you'} (head)`)
    if (isGm) {
      roster.headCoaches
        .filter((h) => h.id !== headId && h.org_prefix !== '117')
        .forEach((h) => addOption(h.id, `@${h.username} (head)`))
      roster.staff.forEach((s) => {
        addOption(s.id, `@${s.username} (line)`)
      })
      return opts
    }
    roster.staff.filter((s) => s.reports_to_id === headId).forEach((s) => {
      addOption(s.id, `@${s.username} (line)`)
    })
    return opts
  }

  const gmAthleteCoachAssignOptions = useMemo(() => {
    const opts = []
    const seen = new Set()
    const addOption = (id, label) => {
      if (id == null || seen.has(id)) return
      seen.add(id)
      opts.push({ id, label })
    }
    ;[...roster.headCoaches]
      .sort((a, b) => a.username.localeCompare(b.username))
      .forEach((h) => {
        const role = prefixForUsername(h.username) === '117' ? 'GMHC' : 'AGMHC'
        addOption(h.id, `@${h.username} (${role})`)
      })
    ;[...roster.staff]
      .sort((a, b) => a.username.localeCompare(b.username))
      .forEach((s) => {
        addOption(s.id, `@${s.username} (LC)`)
      })
    return opts
  }, [roster.headCoaches, roster.staff])

  const scopedAthleteCoachAssignOptions = useMemo(() => {
    if (!headId) return []
    const opts = []
    const seen = new Set()
    const addOption = (id, label) => {
      if (id == null || seen.has(id)) return
      seen.add(id)
      opts.push({ id, label })
    }
    addOption(headId, `@${headUser?.username || 'you'} (head)`)
    roster.staff
      .filter((s) => s.reports_to_id === headId)
      .sort((a, b) => a.username.localeCompare(b.username))
      .forEach((s) => addOption(s.id, `@${s.username} (line)`))
    return opts
  }, [headId, headUser?.username, roster.staff])

  const athleteCoachOptionsForRow = useCallback((athlete) => {
    const base = isGmHeadUser ? gmAthleteCoachAssignOptions : scopedAthleteCoachAssignOptions
    const out = [...base]
    if (
      athlete.primary_coach_id != null
      && !out.some((o) => o.id === athlete.primary_coach_id)
    ) {
      out.push({
        id: athlete.primary_coach_id,
        label: `@${athlete.primary_coach_username || athlete.primary_coach_id} (current)`,
      })
    }
    return out
  }, [gmAthleteCoachAssignOptions, isGmHeadUser, scopedAthleteCoachAssignOptions])

  const headCoachOptions = () => {
    if (roster.headCoaches.length > 0) {
      return roster.headCoaches.map((h) => ({ id: h.id, label: `@${h.username}` }))
    }
    return headId ? [{ id: headId, label: `@${headUser?.username || 'you'}` }] : []
  }

  const availableAgmCategoryOptions = (currentHeadCoach) => {
    const occupied = new Set(
      roster.headCoaches
        .filter((h) => h.id !== currentHeadCoach.id && AGM_CATEGORY_OPTIONS.some((opt) => opt.prefix === h.org_prefix))
        .map((h) => h.org_prefix)
    )
    return AGM_CATEGORY_OPTIONS.filter((opt) => opt.prefix === 'XXX_UNASSIGNED' || !occupied.has(opt.prefix))
  }

  const refreshAll = () => Promise.all([loadSummary(), loadRoster(), loadAnalytics()])

  const renderOrgBadge = (row) => {
    if (!row?.org_label) return null
    return (
      <span className={`head-org-badge head-org-${row.org_color_key || 'graphite'}`}>
        {row.org_label}
      </span>
    )
  }

  const renderSkillBadge = (skillTeam) => {
    const team = SKILL_TEAM_CONFIG.find((item) => item.key === (skillTeam || '')) || SKILL_TEAM_CONFIG[4]
    return <span className={`head-skill-badge head-skill-${team.tone}`}>{team.label}</span>
  }

  const validateProvisioning = () => {
    const headByUsername = new Map(roster.headCoaches.map((h) => [h.username, h]))
    const staffByUsername = new Map(roster.staff.map((s) => [s.username, s]))
    const athleteByUsername = new Map(roster.athletes.map((a) => [a.username, a]))
    const missingHeads = []
    if (!headByUsername.has('117_HeadCoachGM')) missingHeads.push('117_HeadCoachGM')
    EXPECTED_AGM_HEAD_COACHES.forEach((username) => {
      if (!headByUsername.has(username)) missingHeads.push(username)
    })
    const managedHeads = EXPECTED_STANDALONE_HEAD_SUFFIXES.map((suffix) => (
      roster.headCoaches.find((h) => h.username.endsWith(`_${suffix}`))
    ))
    managedHeads.forEach((row, idx) => {
      if (!row) missingHeads.push(`XXX_${EXPECTED_STANDALONE_HEAD_SUFFIXES[idx]}`)
    })
    const missingLineCoaches = EXPECTED_LINE_COACHES.filter((username) => !staffByUsername.has(username))
    const invalidHeadTags = managedHeads.filter(Boolean).filter((row) => (
      row.org_label !== 'XXX_UNASSIGNED' && !AGM_CATEGORY_OPTIONS.some((opt) => opt.prefix === row.org_prefix)
    ))
    const validLineCoachHeadUsernames = new Set([
      '117_HeadCoachGM',
      ...roster.headCoaches
        .filter((h) => AGM_CATEGORY_OPTIONS.some((opt) => opt.prefix !== 'XXX_UNASSIGNED' && opt.prefix === h.org_prefix))
        .map((h) => h.username),
    ])
    const invalidLineCoachAssignments = EXPECTED_LINE_COACHES.filter((username) => {
      const row = staffByUsername.get(username)
      return !row || !validLineCoachHeadUsernames.has(row.reports_to_username)
    })
    const athlete = athleteByUsername.get(EXPECTED_PRIMARY_ATHLETE)
    const validAthleteCoachIds = new Set([
      ...roster.headCoaches.map((h) => h.id),
      ...roster.staff.map((s) => s.id),
    ])
    const invalidUatAthletes = EXPECTED_UNASSIGNED_ATHLETES.filter((username) => {
      const row = athleteByUsername.get(username)
      if (!row) return true
      if (row.primary_coach_id === null) return row.org_label !== 'XXX_UNASSIGNED'
      return !validAthleteCoachIds.has(row.primary_coach_id)
    })

    if (missingHeads.length > 0) {
      window.alert(`Error: missing head coaches: ${missingHeads.join(', ')}`)
      return
    }
    if (invalidHeadTags.length > 0) {
      window.alert(`Error: expected XXX_UNASSIGNED or AGM tags for: ${invalidHeadTags.map((row) => row.username).join(', ')}`)
      return
    }
    if (missingLineCoaches.length > 0) {
      window.alert(`Error: missing line coaches: ${missingLineCoaches.join(', ')}`)
      return
    }
    if (invalidLineCoachAssignments.length > 0) {
      window.alert(`Error: line coaches not assigned to @117_HeadCoachGM or an active AGM head coach: ${invalidLineCoachAssignments.join(', ')}`)
      return
    }
    if (!athlete || athlete.primary_coach_username !== EXPECTED_PRIMARY_COACH) {
      window.alert(`Error: ${EXPECTED_PRIMARY_ATHLETE} is not assigned to @${EXPECTED_PRIMARY_COACH}`)
      return
    }
    if (invalidUatAthletes.length > 0) {
      window.alert(`Error: expected these UAT athletes to be XXX_UNASSIGNED or assigned to an active coach/head coach: ${invalidUatAthletes.join(', ')}`)
      return
    }
    window.alert('Good to go! Head coaches, line coaches, category tags, athlete assignment, and unassigned athlete pool are provisioned.')
  }

  const beginHeadCoachReassign = (headCoach) => {
    setHeadCoachReassignId(headCoach.id)
    setHeadCoachTargetPrefix(headCoach.org_prefix && headCoach.org_prefix !== '117' ? headCoach.org_prefix : 'XXX_UNASSIGNED')
  }

  const cancelHeadCoachReassign = () => {
    setHeadCoachReassignId(null)
    setHeadCoachTargetPrefix('')
  }

  const beginStaffReassign = (staff) => {
    setStaffReassignId(staff.id)
    setStaffTargetId(staff.reports_to_id ?? '')
  }

  const cancelStaffReassign = () => {
    setStaffReassignId(null)
    setStaffTargetId('')
  }

  const handleInvite = async (e) => {
    e.preventDefault()
    const u = inviteUsername.trim()
    if (!u) return
    setAssignBusy(true)
    try {
      await postHeadStaffInvite(u)
      setInviteUsername('')
      showAssignToast(`Linked @${u}.`)
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not add coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleAssignStaff = async (userId, username) => {
    setAssignBusy(true)
    try {
      await patchHeadStaffAssignment(userId, staffTargetId === '' ? null : Number(staffTargetId))
      showAssignToast(staffTargetId === '' ? `Moved @${username} to unaffiliated.` : `Assigned @${username}.`)
      cancelStaffReassign()
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not assign coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleAssignHeadCoach = async (userId, username) => {
    if (!headCoachTargetPrefix) {
      showAssignToast('Choose an AGM category before assigning this head coach.')
      return
    }
    setAssignBusy(true)
    try {
      const result = await patchHeadCoachCategory(userId, headCoachTargetPrefix)
      const action = result.org_label === 'XXX_UNASSIGNED' ? 'Moved' : 'Assigned'
      showAssignToast(`${action} @${username} to ${result.org_label}. New username: @${result.username}.`)
      cancelHeadCoachReassign()
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not assign head coach category.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleDeleteHeadCoach = async (userId, username) => {
    if (!window.confirm(`Delete head coach @${username}? The account will be blocked and recoverable for 30 days.`)) return
    setAssignBusy(true)
    try {
      await deleteHeadCoach(userId)
      showAssignToast(`Deleted head coach @${username}. Account is recoverable for 30 days.`)
      cancelHeadCoachReassign()
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not delete head coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleDeleteStaff = async (userId, username) => {
    if (!window.confirm(`Delete coach @${username}? The account will be blocked and recoverable for 30 days.`)) return
    setAssignBusy(true)
    try {
      await deleteHeadStaff(userId)
      showAssignToast(`Deleted coach @${username}. Account is recoverable for 30 days.`)
      cancelStaffReassign()
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not delete coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleAthleteCoachChange = async (athleteId, primaryCoachId, username = 'athlete') => {
    setAssignBusy(true)
    try {
      const target = primaryCoachId === '' ? null : Number(primaryCoachId)
      await patchHeadAthletePrimaryCoach(athleteId, target)
      showAssignToast(target == null ? `Moved @${username} to unaffiliated.` : `Assigned @${username}.`)
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not update athlete coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleAthleteSkillTeamChange = async (athleteId, skillTeam, username = 'athlete') => {
    setAssignBusy(true)
    try {
      await patchHeadAthleteSkillTeam(athleteId, skillTeam)
      showAssignToast(
        skillTeam
          ? `Updated @${username} skill team to ${skillTeam}.`
          : `Cleared skill team for @${username} (NO TEAM).`,
      )
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Skill-team request required or blocked by access rules.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleDeleteAthlete = async (athleteId, username) => {
    if (!window.confirm(`Delete @${username}? The account will be blocked and recoverable for 30 days.`)) return
    setAssignBusy(true)
    try {
      await deleteHeadAthlete(athleteId)
      showAssignToast(`Deleted @${username}. Account is recoverable for 30 days.`)
      await refreshAll()
    } catch (err) {
      showAssignToast(formatApiError(err, 'Could not delete athlete.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const renderSkillTeamSections = (sections, { showDeleteActions = false } = {}) => (
    <div className="head-skill-team-stack">
      {sections.map((section) => (
        <section
          key={section.key || 'unassigned'}
          className={`head-skill-team-section head-skill-team-${section.tone}`}
          aria-label={section.label}
        >
          <div className="head-skill-team-heading">
            {renderSkillBadge(section.key)}
            <span>{section.athletes.length} athlete(s)</span>
          </div>
          <div className="head-skill-team-table-wrap">
            <table
              className={`head-table head-skill-roster-table ${showDeleteActions ? 'head-skill-roster-table--actions' : ''}`}
            >
            <thead>
              <tr>
                <th>Athlete</th>
                <th>Skill team</th>
                <th>Accountable coach</th>
                {showDeleteActions && <th className="head-actions-col">Action</th>}
              </tr>
            </thead>
            <tbody>
              {section.athletes.map((a) => (
                <tr key={a.id}>
                  <td className="head-athlete-person-cell">
                    <span className="head-identity">
                      <span className="username-highlight">@{a.username}</span>
                      {renderOrgBadge(a)}
                    </span>
                  </td>
                  <td className="head-skill-cell">
                    <select
                      className="head-coach-select head-skill-select"
                      value={a.skill_team || ''}
                      disabled={assignBusy}
                      aria-label={`Skill team for ${a.username}`}
                      onChange={(ev) => handleAthleteSkillTeamChange(a.id, ev.target.value, a.username)}
                    >
                      <option value="">NO TEAM</option>
                      {SKILL_TEAM_CONFIG.filter((team) => team.key).map((team) => (
                        <option key={team.key} value={team.key}>{team.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="head-accountable-cell">
                    <select
                      className="head-coach-select head-accountable-select"
                      value={a.primary_coach_id ?? ''}
                      disabled={assignBusy || !headId}
                      aria-label={`Accountable coach for ${a.username}`}
                      onChange={(ev) => handleAthleteCoachChange(a.id, ev.target.value, a.username)}
                    >
                      <option value="">XXX_UNASSIGNED</option>
                      {athleteCoachOptionsForRow(a).map((opt) => (
                        <option key={opt.id} value={opt.id}>{opt.label}</option>
                      ))}
                    </select>
                  </td>
                  {showDeleteActions && (
                    <td className="head-actions-cell">
                      <span className="head-athlete-actions">
                        <button
                          type="button"
                          className="head-btn-danger"
                          disabled={assignBusy}
                          onClick={() => handleDeleteAthlete(a.id, a.username)}
                        >
                          Delete
                        </button>
                      </span>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      ))}
    </div>
  )

  return (
    <div className="dashboard-container head-dashboard">
      {assignToast && (
        <div
          className={`head-assign-toast save-message ${assignToast.kind}`}
          role="status"
          aria-live="polite"
          onMouseEnter={() => setAssignToastHovered(true)}
          onMouseLeave={() => setAssignToastHovered(false)}
        >
          {assignToast.message}
        </div>
      )}

      <header className="dashboard-header head-dashboard-header">
        <div>
          <div className="dashboard-kicker-row">
            <span className="dashboard-kicker">{accessMeta.shortLabel}</span>
            <Link to="/coach" className="head-dashboard-link-coach">Open coach workspace</Link>
          </div>
          <h1>{accessMeta.title}</h1>
          <p className="dashboard-description head-dashboard-lede">
            {accessMeta.description}
          </p>
        </div>
      </header>

      <section className="head-workspace-shell section-card" aria-label="UAT 3.0 role workspaces">
        <div>
          <span className="head-access-label">{accessMeta.scope}</span>
          <p>
            MVP-first UAT 3.0 shell: head-coach view, line-coach context, schedule, settings, and the global Light/Dark plus Simple/Complex controls.
          </p>
        </div>
        <div className="head-workspace-tabs" role="tablist" aria-label="Head dashboard workspaces">
          {workspaceTabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`head-workspace-tab ${activeWorkspace === tab.key ? 'active' : ''}`}
              role="tab"
              aria-selected={activeWorkspace === tab.key}
              onClick={() => setActiveWorkspace(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {activeWorkspace === 'head' && (
      <>
      <section className="summary-grid head-summary-grid" aria-label="Head coach summary metrics">
        <article className="home-metric section-card">
          <span className="label">Coaches in org</span>
          <span className="value data">{summaryTotals.coaches}</span>
        </article>
        <article className="home-metric section-card">
          <span className="label">Athletes managed</span>
          <span className="value data">{summaryTotals.athletes}</span>
        </article>
        <article className="home-metric section-card">
          <span className="label">Programs tracked</span>
          <span className="value data">{summaryTotals.programs}</span>
        </article>
        {SHOW_HEAD_ANALYTICS && (
          <article className="home-metric section-card">
            <span className="label">Recommendation cards</span>
            <span className="value data">{summaryTotals.recommendationCount}</span>
          </article>
        )}
        <article className="home-metric section-card">
          <span className="label">Programs with PR data</span>
          <span className="value data">{summaryTotals.prs}</span>
        </article>
        <article className="home-metric section-card">
          <span className="label">Workout logs</span>
          <span className="value data">{summaryTotals.workoutLogs}</span>
        </article>
      </section>

      {loading && <p className="head-dashboard-status">Loading summary…</p>}
      {error && <div className="save-message error">{error}</div>}

      {!loading && !error && (
        <div className="head-table-wrap section-card">
          <table className="head-table">
            <thead>
              <tr>
                <th>Coach</th>
                <th>Role</th>
                <th>Athletes</th>
                <th>Programs</th>
                <th>PRs</th>
                <th>Workout logs</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td><span className="username-highlight">@{row.username}</span></td>
                  <td>{row.user_type === 'head_coach' ? 'Head' : 'Line'}</td>
                  <td>{row.athlete_count}</td>
                  <td>{row.program_count}</td>
                  <td>{row.personal_record_count}</td>
                  <td>{row.workout_log_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {SHOW_HEAD_ANALYTICS && (
      <section className="head-model-strip section-card" aria-labelledby="head-model-strip-title">
        <div>
          <h2 id="head-model-strip-title">Recommendation engine</h2>
          <p className="head-assign-lede">
            Predictive guidance is de-identified and segment-based. Model and rule fallback status are shown here.
          </p>
        </div>
        <div className="head-model-cards">
          <article className="head-model-card">
            <span className="label">Engine mode</span>
            <strong className="data">{String(analytics.strategy || 'rule').toUpperCase()}</strong>
          </article>
          <article className="head-model-card">
            <span className="label">Model version</span>
            <strong className="data">{analytics.modelVersion || 'N/A'}</strong>
          </article>
          <article className="head-model-card">
            <span className="label">Last generated</span>
            <strong className="data">
              {analytics.generatedAt ? new Date(analytics.generatedAt).toLocaleString() : 'N/A'}
            </strong>
          </article>
          <article className="head-model-card">
            <span className="label">Artifact freshness</span>
            <strong className="data">
              {analytics.modelStatus?.latest_model?.trained_at ? new Date(analytics.modelStatus.latest_model.trained_at).toLocaleDateString() : 'Not trained'}
            </strong>
          </article>
        </div>
        {analytics.fallbackReason && (
          <div className="save-message warning">
            Fallback active: {analytics.fallbackReason}
          </div>
        )}
        {topRecommendation && (
          <p className="head-top-recommendation">
            Top segment insight: <span className="data">{topRecommendation.segment.gender}/{topRecommendation.segment.bodyweight_bucket}/{topRecommendation.segment.weight_class}</span> performs best with <span className="data">{topRecommendation.recommended_style_tag}</span>.
          </p>
        )}
      </section>
      )}

      {SHOW_HEAD_ANALYTICS && (
      <section className="head-analytics-section section-card" aria-labelledby="head-analytics-heading">
        <h2 id="head-analytics-heading" className="head-assign-title">De-identified analytics</h2>
        <p className="head-assign-lede">
          Aggregated athlete segments only. Sparse cohorts are hidden below sample size {analytics.minimumSampleSize}.
        </p>
        {analyticsError && <div className="save-message error">{analyticsError}</div>}

        <div className="head-assign-card">
          <h3>Program style outcomes</h3>
          {analytics.styleGroups.length === 0 ? (
            <p className="head-assign-empty">Not enough data yet for style outcomes.</p>
          ) : (
            <table className="head-table head-athlete-table">
              <thead>
                <tr>
                  <th>Style</th>
                  <th>Segment</th>
                  <th>Sample</th>
                  <th>Completion rate</th>
                  <th>Avg PR delta (kg)</th>
                </tr>
              </thead>
              <tbody>
                {analytics.styleGroups.slice(0, 16).map((group, idx) => (
                  <tr key={`${group.style_tag}-${idx}`}>
                    <td>{group.style_tag}</td>
                    <td>{group.segment.gender}/{group.segment.bodyweight_bucket}/{group.segment.weight_class}</td>
                    <td>{group.metrics.sample_size}</td>
                    <td>{group.metrics.completion_rate == null ? '—' : `${Math.round(group.metrics.completion_rate * 100)}%`}</td>
                    <td>{group.metrics.avg_pr_delta_kg == null ? '—' : group.metrics.avg_pr_delta_kg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="head-assign-card">
          <h3>Normalized program name outcomes</h3>
          {analytics.nameGroups.length === 0 ? (
            <p className="head-assign-empty">Not enough data yet for normalized-name outcomes.</p>
          ) : (
            <table className="head-table head-athlete-table">
              <thead>
                <tr>
                  <th>Normalized name</th>
                  <th>Sample</th>
                  <th>Completion rate</th>
                  <th>Avg PR delta (kg)</th>
                </tr>
              </thead>
              <tbody>
                {analytics.nameGroups.slice(0, 12).map((group) => (
                  <tr key={group.normalized_name}>
                    <td>{group.normalized_name}</td>
                    <td>{group.metrics.sample_size}</td>
                    <td>{group.metrics.completion_rate == null ? '—' : `${Math.round(group.metrics.completion_rate * 100)}%`}</td>
                    <td>{group.metrics.avg_pr_delta_kg == null ? '—' : group.metrics.avg_pr_delta_kg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="head-assign-card">
          <h3>Segment recommendations</h3>
          {analytics.recommendations.length === 0 ? (
            <p className="head-assign-empty">Insufficient data for recommendations.</p>
          ) : (
            <ul className="head-analytics-recs">
              {analytics.recommendations.slice(0, 10).map((rec, idx) => (
                <li key={`${rec.recommended_style_tag}-${idx}`}>
                  <span className="data">{rec.segment.gender}/{rec.segment.bodyweight_bucket}/{rec.segment.weight_class}</span>
                  <span> → {rec.recommended_style_tag}</span>
                  <span className="head-analytics-rec-meta">
                    n={rec.confidence.sample_size}, completion {rec.confidence.effect.completion_rate == null ? '—' : `${Math.round(rec.confidence.effect.completion_rate * 100)}%`}, avg PR Δ {rec.confidence.effect.avg_pr_delta_kg == null ? '—' : `${rec.confidence.effect.avg_pr_delta_kg}kg`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      )}

      <section className="head-assign-section section-card" aria-labelledby="head-assign-heading">
        <h2 id="head-assign-heading" className="head-assign-title">Assignments</h2>
        <p className="head-assign-lede">
          Add line coaches by username or claim available coaches. Set each athlete&apos;s accountable coach.
        </p>

        {rosterLoading && <p className="head-dashboard-status">Loading roster…</p>}
        {rosterError && <div className="save-message error">{rosterError}</div>}

        {!rosterLoading && !rosterError && (
          <>
            <form className="head-invite-form" onSubmit={handleInvite}>
              <label htmlFor="head-invite-user" className="sr-only">Coach username</label>
              <input
                id="head-invite-user"
                type="text"
                autoComplete="username"
                placeholder="Line coach username"
                value={inviteUsername}
                onChange={(ev) => setInviteUsername(ev.target.value)}
                disabled={assignBusy}
              />
              <button type="submit" className="head-btn-primary" disabled={assignBusy}>
                Add to org
              </button>
            </form>

            <div className="head-assign-card">
              <h3>Head coach categories</h3>
              <div className="head-file-cabinet">
                <div className="head-file-tabs" role="tablist" aria-label="Head coach category files">
                {visibleHeadCategoryLinks.map((category) => (
                  <button
                    key={category.prefix}
                    type="button"
                    className={`head-file-tab ${activeHeadCategory === category.prefix ? 'active' : ''}`}
                    role="tab"
                    aria-selected={activeHeadCategory === category.prefix}
                    aria-controls="head-category-panel"
                    onClick={() => setActiveHeadCategory(category.prefix)}
                  >
                    {category.label}
                  </button>
                ))}
                </div>
                <div
                  id="head-category-panel"
                  className={`head-file-panel head-file-panel-${selectedHeadCategory.colorKey}`}
                  role="tabpanel"
                >
                  <div className="head-file-panel-summary">
                    <span className={`head-org-badge head-org-${selectedHeadCategory.colorKey}`}>
                      {selectedHeadCategory.label}
                    </span>
                    <span className="head-file-panel-title">
                      {selectedCategoryLead
                        ? `@${selectedCategoryLead.username}`
                        : selectedHeadCategory.username === 'UNASSIGNED'
                          ? selectedHeadCategory.username
                          : `@${selectedHeadCategory.username}`}
                    </span>
                    <span className="head-file-panel-meta">{selectedCategoryStatus}</span>
                    {selectedHeadCategory.prefix === '117' && (
                      <button
                        type="button"
                        className="head-btn-secondary head-provision-check"
                        onClick={validateProvisioning}
                      >
                        Validate provisioning
                      </button>
                    )}
                  </div>

                  {selectedHeadCategory.prefix === '117' ? (
                    <div className="head-file-dashboard">
                      <div className="head-assign-card">
                        <h3>Head coaches</h3>
                        {roster.headCoaches.length === 0 ? (
                          <p className="head-assign-empty">No head coach accounts yet.</p>
                        ) : (
                          <table className="head-table head-head-table">
                            <thead>
                              <tr>
                                <th>Head coach</th>
                                <th>Category tag</th>
                                <th>Status</th>
                                <th className="head-actions-col">Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {roster.headCoaches.map((h) => (
                                <tr key={h.id}>
                                  <td className="head-head-person-cell">
                                    <span className="head-identity">
                                      <span className="username-highlight">@{h.username}</span>
                                    </span>
                                  </td>
                                  <td className="head-category-cell">{renderOrgBadge(h)}</td>
                                  <td className="head-status-cell">
                                    {h.org_prefix === '117' ? 'GM Head Coach' : h.org_prefix ? 'AGM Head Coach' : 'Unaffiliated'}
                                  </td>
                                  {h.org_prefix === '117' ? (
                                    <td className="head-actions-cell">
                                      <span className="head-muted-action">Locked</span>
                                    </td>
                                  ) : headCoachReassignId === h.id ? (
                                    <td className="head-actions-cell">
                                      <span className="head-athlete-actions">
                                        <select
                                          className="head-coach-select"
                                          value={headCoachTargetPrefix}
                                          disabled={assignBusy}
                                          onChange={(ev) => setHeadCoachTargetPrefix(ev.target.value)}
                                        >
                                          <option value="">Choose category</option>
                                          {availableAgmCategoryOptions(h).map((opt) => (
                                            <option key={opt.prefix} value={opt.prefix}>{opt.label}</option>
                                          ))}
                                        </select>
                                        <button
                                          type="button"
                                          className="head-btn-primary"
                                          disabled={assignBusy || !headCoachTargetPrefix}
                                          onClick={() => handleAssignHeadCoach(h.id, h.username)}
                                        >
                                          Assign
                                        </button>
                                        <button
                                          type="button"
                                          className="head-btn-secondary"
                                          disabled={assignBusy}
                                          onClick={cancelHeadCoachReassign}
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          type="button"
                                          className="head-btn-danger"
                                          disabled={assignBusy}
                                          onClick={() => handleDeleteHeadCoach(h.id, h.username)}
                                        >
                                          Delete
                                        </button>
                                      </span>
                                    </td>
                                  ) : (
                                    <td className="head-actions-cell">
                                      <span className="head-athlete-actions">
                                        <button
                                          type="button"
                                          className="head-btn-warning"
                                          disabled={assignBusy}
                                          onClick={() => beginHeadCoachReassign(h)}
                                        >
                                          {h.org_prefix ? 'Reassign' : 'Assign'}
                                        </button>
                                        <button
                                          type="button"
                                          className="head-btn-danger"
                                          disabled={assignBusy}
                                          onClick={() => handleDeleteHeadCoach(h.id, h.username)}
                                        >
                                          Delete
                                        </button>
                                      </span>
                                    </td>
                                  )}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>

                      <div className="head-assign-card">
                        <h3>Line coaches</h3>
                        {roster.staff.length === 0 ? (
                          <p className="head-assign-empty">No line coaches or available coach accounts yet.</p>
                        ) : (
                          <table className="head-table head-roster-table">
                            <thead>
                              <tr>
                                <th>Line coach</th>
                                <th>Accountable coach</th>
                                <th className="head-actions-col">Action</th>
                              </tr>
                            </thead>
                            <tbody>
                            {roster.staff.map((s, idx) => (
                              <tr
                                key={s.id}
                                className={`head-coach-row head-coach-accent-${COACH_ACCENT_CLASSES[idx % COACH_ACCENT_CLASSES.length]}`}
                              >
                                <td className="head-roster-person-cell">
                                  <span className="head-identity">
                                    <span className="username-highlight">@{s.username}</span>
                                    {renderOrgBadge(s)}
                                  </span>
                                </td>
                                <td className="head-accountable-cell">
                                  {s.reports_to_id ? `@${s.reports_to_username || s.reports_to_id}` : 'Unaffiliated'}
                                </td>
                                {staffReassignId === s.id ? (
                                  <td className="head-actions-cell">
                                    <span className="head-athlete-actions">
                                    <select
                                      className="head-coach-select"
                                      value={staffTargetId}
                                      disabled={assignBusy}
                                      onChange={(ev) => setStaffTargetId(ev.target.value)}
                                    >
                                      <option value="">Unaffiliated</option>
                                      {headCoachOptions().map((opt) => (
                                        <option key={opt.id} value={opt.id}>{opt.label}</option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      className="head-btn-primary"
                                      disabled={assignBusy}
                                      onClick={() => handleAssignStaff(s.id, s.username)}
                                    >
                                      Assign
                                    </button>
                                    <button
                                      type="button"
                                      className="head-btn-secondary"
                                      disabled={assignBusy}
                                      onClick={cancelStaffReassign}
                                    >
                                      Cancel
                                    </button>
                                    <button
                                      type="button"
                                      className="head-btn-danger"
                                      disabled={assignBusy}
                                      onClick={() => handleDeleteStaff(s.id, s.username)}
                                    >
                                      Delete
                                    </button>
                                    </span>
                                  </td>
                                ) : (
                                  <td className="head-actions-cell">
                                    <span className="head-athlete-actions">
                                    <button
                                      type="button"
                                      className="head-btn-warning"
                                      disabled={assignBusy}
                                      onClick={() => beginStaffReassign(s)}
                                    >
                                      Reassign
                                    </button>
                                    <button
                                      type="button"
                                      className="head-btn-danger"
                                      disabled={assignBusy}
                                      onClick={() => handleDeleteStaff(s.id, s.username)}
                                    >
                                      Delete
                                    </button>
                                    </span>
                                  </td>
                                )}
                              </tr>
                            ))}
                            </tbody>
                          </table>
                        )}
                      </div>

                      <div className="head-assign-card" data-head-ui="skill-roster-2026-05-05">
                        <h3>Athletes</h3>
                        {roster.athletes.length === 0 ? (
                          <p className="head-assign-empty">No athletes or available athlete accounts yet.</p>
                        ) : (
                          renderSkillTeamSections(allSkillTeamSections, { showDeleteActions: true })
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="head-file-dashboard">
                      {!selectedCategoryLead ? (
                        <div className="head-file-empty">
                          <strong>{selectedHeadCategory.label}</strong>
                          <span>No AGMHC, line coaches, or athletes are assigned to this category yet.</span>
                        </div>
                      ) : (
                        <>
                          <div className="head-category-summary-grid">
                            <article className="home-metric section-card">
                              <span className="label">AGMHC</span>
                              <span className="value data">1</span>
                            </article>
                            <article className="home-metric section-card">
                              <span className="label">Line coaches</span>
                              <span className="value data">{selectedCategoryRoster.staff.length}</span>
                            </article>
                            <article className="home-metric section-card">
                              <span className="label">Athletes</span>
                              <span className="value data">{selectedCategoryRoster.athletes.length}</span>
                            </article>
                          </div>

                          <div className="head-assign-card">
                            <h3>AGM Head Coach</h3>
                            <table className="head-table head-head-table">
                              <thead>
                                <tr>
                                  <th>Head coach</th>
                                  <th>Category tag</th>
                                  <th>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {selectedCategoryRoster.headCoaches.map((h) => (
                                  <tr key={h.id}>
                                    <td><span className="username-highlight">@{h.username}</span></td>
                                    <td>{renderOrgBadge(h)}</td>
                                    <td>AGM Head Coach</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          <div className="head-assign-card">
                            <h3>Line coaches</h3>
                            {selectedCategoryRoster.staff.length === 0 ? (
                              <p className="head-assign-empty">No line coaches assigned to this category yet.</p>
                            ) : (
                              <table className="head-table head-roster-table">
                                <thead>
                                  <tr>
                                    <th>Line coach</th>
                                    <th>Accountable coach</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectedCategoryRoster.staff.map((s) => (
                                    <tr key={s.id}>
                                      <td>
                                        <span className="head-identity">
                                          <span className="username-highlight">@{s.username}</span>
                                          {renderOrgBadge(s)}
                                        </span>
                                      </td>
                                      <td>{s.reports_to_username ? `@${s.reports_to_username}` : 'Unaffiliated'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>

                          <div className="head-assign-card" data-head-ui="skill-roster-2026-05-05">
                            <h3>Athletes</h3>
                            {selectedCategoryRoster.athletes.length === 0 ? (
                              <p className="head-assign-empty">No athletes assigned to this category yet.</p>
                            ) : (
                              renderSkillTeamSections(selectedSkillTeamSections)
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </section>
      </>
      )}

      {activeWorkspace === 'line' && (
        <section className="head-uat-panel section-card" aria-labelledby="line-coach-workspace-heading">
          <div className="head-panel-heading">
            <span className="head-access-label">LC workspace</span>
            <h2 id="line-coach-workspace-heading">Line coach view</h2>
          </div>
          <p>
            Line coaches keep the narrowest data wall: their assigned athletes, assigned programs, PRs, workout logs, and their own account/certification details.
          </p>
          <div className="head-mvp-grid">
            <article className="head-mvp-card">
              <h3>Current MVP link</h3>
              <p>Use the existing coach workspace for programming and athlete execution tools.</p>
              <Link to="/coach" className="head-dashboard-link-coach">Open line-coach workspace</Link>
            </article>
            <article className="head-mvp-card">
              <h3>Access wall</h3>
              <p>GMHC may see all LC data. AGMHC sees only assigned LCs. LC sees only their own athlete tree.</p>
            </article>
          </div>
        </section>
      )}

      {activeWorkspace === 'schedule' && (
        <section className="head-uat-panel section-card" aria-labelledby="schedule-workspace-heading">
          <div className="head-panel-heading">
            <span className="head-access-label">Priority 2</span>
            <h2 id="schedule-workspace-heading">Schedule</h2>
          </div>
          <p>
            Spreadsheet-first staff coverage view. GMHC owns edits in MVP; AGMHC and LC users begin with read-only schedule visibility unless GMHC delegates access later.
          </p>
          <div className="head-schedule-tools">
            <button type="button" className="head-btn-secondary">Daily outlook</button>
            <button type="button" className="head-btn-secondary">Weekly outlook</button>
            <button type="button" className="head-btn-secondary">Monthly outlook</button>
          </div>
          <div className="head-schedule-grid" role="table" aria-label="MVP weekly coach schedule">
            {SCHEDULE_DAYS.map((day, idx) => (
              <article className="head-schedule-day" key={day} role="row">
                <strong>{day}</strong>
                <span>{scheduleCoachNames[idx % scheduleCoachNames.length]}</span>
                <small>{isGmHeadUser ? 'GM editable placeholder' : 'Read-only placeholder'}</small>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeWorkspace === 'settings' && (
        <section className="head-uat-panel section-card" aria-labelledby="settings-workspace-heading">
          <div className="head-panel-heading">
            <span className="head-access-label">Priority 1</span>
            <h2 id="settings-workspace-heading">Settings</h2>
          </div>
          <p>
            Settings are role-aware. GMHC gets organization-level controls, AGMHC gets assigned-team controls, LC gets self and athlete-management tools, and athletes keep account/profile controls.
          </p>
          <div className="head-mvp-grid">
            <article className="head-mvp-card">
              <h3>Account profile</h3>
              <ul>
                <li>Display name and username suffix edits, with the protected <span className="data">@###_</span> prefix called out.</li>
                <li>Email verification/change and phone number fields.</li>
                <li>Athlete card: DOB/age, gender, bodyweight, and opt-in privacy note for model quality.</li>
              </ul>
            </article>
            <article className="head-mvp-card">
              <h3>Access controls</h3>
              <ul>
                <li>GMHC: global org, settings, compliance, schedule, and delegation controls.</li>
                <li>AGMHC: assigned coaches and athletes only, plus delegated tools.</li>
                <li>LC: own profile, certifications, and assigned athlete management only.</li>
              </ul>
            </article>
          </div>
          <div className="head-assign-card">
            <h3>Coach certifications</h3>
            <p className="head-assign-lede">
              MVP compliance tracker for CPR/AED, USAW, ACPT/NCCA or equivalent nationally accredited personal-training certificates, and gym/class safety requirements.
            </p>
            <table className="head-table head-cert-table">
              <thead>
                <tr>
                  <th>Coach</th>
                  <th>Role</th>
                  <th>Visibility</th>
                  {CERTIFICATION_TYPES.map((cert) => <th key={cert}>{cert}</th>)}
                </tr>
              </thead>
              <tbody>
                {certificationRows.map((coach) => (
                  <tr key={coach.id}>
                    <td><span className="username-highlight">@{coach.username}</span></td>
                    <td>{coach.role}</td>
                    <td>{coach.scope}</td>
                    {CERTIFICATION_TYPES.map((cert) => <td key={cert}>Date needed</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

export default HeadCoachDashboard
