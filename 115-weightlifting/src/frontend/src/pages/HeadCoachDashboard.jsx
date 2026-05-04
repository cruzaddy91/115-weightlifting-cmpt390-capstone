import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getHeadProgramNameOutcomes,
  getHeadModelStatus,
  getHeadOrgRoster,
  getHeadOrgSummary,
  getHeadProgramStyleOutcomes,
  getHeadRecommendations,
  patchHeadAthletePrimaryCoach,
  patchHeadStaffLink,
  postHeadStaffInvite,
} from '../services/api'
import { getCurrentUser } from '../utils/auth'
import { formatApiError } from '../utils/errors'
import './HeadCoachDashboard.css'

const HeadCoachDashboard = () => {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [roster, setRoster] = useState({ staff: [], athletes: [] })
  const [rosterLoading, setRosterLoading] = useState(true)
  const [rosterError, setRosterError] = useState('')
  const [inviteUsername, setInviteUsername] = useState('')
  const [assignBusy, setAssignBusy] = useState(false)
  const [assignMessage, setAssignMessage] = useState('')
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
  const headId = headUser?.id
  const summaryTotals = useMemo(() => {
    const totals = {
      coaches: rows.length,
      athletes: 0,
      programs: 0,
      prs: 0,
      workoutLogs: 0,
      styleGroups: analytics.styleGroups.length,
      recommendationCount: analytics.recommendations.length,
    }
    for (const row of rows) {
      totals.athletes += Number(row.athlete_count || 0)
      totals.programs += Number(row.program_count || 0)
      totals.prs += Number(row.personal_record_count || 0)
      totals.workoutLogs += Number(row.workout_log_count || 0)
    }
    return totals
  }, [rows, analytics.styleGroups.length, analytics.recommendations.length])

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
          athletes: data.athletes || [],
        })
        setRosterError('')
      })
      .catch((err) => {
        setRosterError(formatApiError(err, 'Could not load roster.'))
      })
  }, [])

  const loadAnalytics = () => {
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

  const coachOptions = () => {
    if (!headId) return []
    const opts = [{ id: headId, label: `@${headUser?.username || 'you'} (head)` }]
    roster.staff.forEach((s) => {
      opts.push({ id: s.id, label: `@${s.username} (line)` })
    })
    return opts
  }

  const refreshAll = () => Promise.all([loadSummary(), loadRoster(), loadAnalytics()])

  const handleInvite = async (e) => {
    e.preventDefault()
    const u = inviteUsername.trim()
    if (!u) return
    setAssignBusy(true)
    setAssignMessage('')
    try {
      await postHeadStaffInvite(u)
      setInviteUsername('')
      setAssignMessage(`Linked @${u}.`)
      await refreshAll()
    } catch (err) {
      setAssignMessage(formatApiError(err, 'Could not add coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleUnlinkStaff = async (userId, username) => {
    if (!window.confirm(`Remove @${username} from your org?`)) return
    setAssignBusy(true)
    setAssignMessage('')
    try {
      await patchHeadStaffLink(userId, false)
      setAssignMessage(`Removed @${username}.`)
      await refreshAll()
    } catch (err) {
      setAssignMessage(formatApiError(err, 'Could not remove coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const handleAthleteCoachChange = async (athleteId, primaryCoachId) => {
    setAssignBusy(true)
    setAssignMessage('')
    try {
      await patchHeadAthletePrimaryCoach(athleteId, Number(primaryCoachId))
      setAssignMessage('Athlete coach updated.')
      await refreshAll()
    } catch (err) {
      setAssignMessage(formatApiError(err, 'Could not update athlete coach.'))
    } finally {
      setAssignBusy(false)
    }
  }

  return (
    <div className="dashboard-container head-dashboard">
      <header className="dashboard-header head-dashboard-header">
        <div>
          <div className="dashboard-kicker-row">
            <span className="dashboard-kicker">Head Coach</span>
            <Link to="/coach" className="head-dashboard-link-coach">Open coach workspace</Link>
          </div>
          <h1>Organization overview</h1>
          <p className="dashboard-description head-dashboard-lede">
            Org-wide roster health, program outcomes, and model-guided training signals in one executive view.
          </p>
        </div>
      </header>

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
        <article className="home-metric section-card">
          <span className="label">Recommendation cards</span>
          <span className="value data">{summaryTotals.recommendationCount}</span>
        </article>
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

      <section className="head-assign-section section-card" aria-labelledby="head-assign-heading">
        <h2 id="head-assign-heading" className="head-assign-title">Assignments</h2>
        <p className="head-assign-lede">
          Add line coaches by username. Set each athlete&apos;s accountable coach (you or a line coach under you).
        </p>

        {rosterLoading && <p className="head-dashboard-status">Loading roster…</p>}
        {rosterError && <div className="save-message error">{rosterError}</div>}
        {assignMessage && (
          <div className={assignMessage.includes('Could not') ? 'save-message error' : 'save-message'}>
            {assignMessage}
          </div>
        )}

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
              <h3>Line coaches</h3>
              {roster.staff.length === 0 ? (
                <p className="head-assign-empty">No line coaches yet.</p>
              ) : (
                <ul className="head-assign-list">
                  {roster.staff.map((s) => (
                    <li key={s.id}>
                      <span className="username-highlight">@{s.username}</span>
                      <button
                        type="button"
                        className="head-btn-danger"
                        disabled={assignBusy}
                        onClick={() => handleUnlinkStaff(s.id, s.username)}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="head-assign-card">
              <h3>Athletes</h3>
              {roster.athletes.length === 0 ? (
                <p className="head-assign-empty">No athletes in your org yet (set primary coach).</p>
              ) : (
                <table className="head-table head-athlete-table">
                  <thead>
                    <tr>
                      <th>Athlete</th>
                      <th>Accountable coach</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roster.athletes.map((a) => (
                      <tr key={a.id}>
                        <td><span className="username-highlight">@{a.username}</span></td>
                        <td>
                          <select
                            className="head-coach-select"
                            value={a.primary_coach_id ?? ''}
                            disabled={assignBusy || !headId}
                            onChange={(ev) => handleAthleteCoachChange(a.id, ev.target.value)}
                          >
                            {coachOptions().map((opt) => (
                              <option key={opt.id} value={opt.id}>{opt.label}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  )
}

export default HeadCoachDashboard
