import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import { buildChartJsCommonOptions, useChartPalette } from '../utils/chartTheme'
import {
  rosterAverageMonthlyBestPrLineData,
  rosterAverageRollingPeakTotalLine,
} from '../utils/trainingCharts'
import { ensureAthleteTrainingChartsRegistered } from './AthleteTrainingTrendCharts'

ensureAthleteTrainingChartsRegistered()

/**
 * Coach home (roster): arithmetic mean of per-athlete monthly bests and of
 * six-month rolling peak totals, across `recordsPerAthlete` (one array per athlete).
 */
export default function CoachRosterAggregateCharts({
  recordsPerAthlete,
  athleteCount,
  loading,
  error,
}) {
  const chartPalette = useChartPalette()

  const monthlyAvg = useMemo(
    () => rosterAverageMonthlyBestPrLineData(recordsPerAthlete, ['snatch', 'clean_jerk', 'total'], chartPalette),
    [recordsPerAthlete, chartPalette],
  )

  const rollingAvg = useMemo(
    () => rosterAverageRollingPeakTotalLine(recordsPerAthlete, chartPalette),
    [recordsPerAthlete, chartPalette],
  )

  const sharedChartOptions = useMemo(
    () => buildChartJsCommonOptions(chartPalette),
    [chartPalette],
  )

  const hasAnyPr = recordsPerAthlete.some((recs) => Array.isArray(recs) && recs.length > 0)
  const showCharts = hasAnyPr && (monthlyAvg.labels.length > 0 || rollingAvg.labels.length > 0)

  return (
    <section className="section-card coach-roster-aggregate-charts" aria-labelledby="coach-roster-charts-heading">
      <h2 id="coach-roster-charts-heading" className="coach-roster-aggregate-charts-title">Roster averages</h2>
      <p className="athlete-charts-intro coach-roster-aggregate-charts-intro">
        Mean of each assigned athlete&apos;s own monthly bests and six-month rolling peak on competition total.
        Athletes without a logged value in a month are excluded from that month&apos;s average (not treated as zero).
      </p>
      {error && (
        <p className="section-subtitle coach-athlete-pr-charts-error" role="alert">{error}</p>
      )}
      {loading && !error && (
        <div className="loading coach-athlete-pr-charts-loading">Loading roster PR data…</div>
      )}
      {!loading && !error && athleteCount === 0 && (
        <p className="section-subtitle">Assign programs to athletes to see roster-level trends.</p>
      )}
      {!loading && !error && athleteCount > 0 && !hasAnyPr && (
        <p className="section-subtitle">No PRs logged yet across this roster — charts appear once athletes log lifts.</p>
      )}
      {!loading && !error && athleteCount > 0 && hasAnyPr && !showCharts && (
        <p className="section-subtitle">PR rows are present but do not yet form a chartable month series for this roster.</p>
      )}
      {!loading && !error && showCharts && (
        <div className="coach-roster-aggregate-charts-grid">
          <div className="chart-card">
            <h4>Avg PR trend (monthly best)</h4>
            {monthlyAvg.labels.length === 0 ? (
              <div className="chart-empty">No overlapping monthly PR data to average.</div>
            ) : (
              <Line data={monthlyAvg} options={sharedChartOptions} />
            )}
          </div>
          <div className="chart-card">
            <h4>Avg rolling strength (6-mo peak total)</h4>
            {rollingAvg.labels.length === 0 ? (
              <div className="chart-empty">Log competition totals to see averaged rolling peaks.</div>
            ) : (
              <Line data={rollingAvg} options={sharedChartOptions} />
            )}
          </div>
        </div>
      )}
    </section>
  )
}
