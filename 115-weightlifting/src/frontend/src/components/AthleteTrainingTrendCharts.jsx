import { useMemo } from 'react'
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { buildChartJsCommonOptions, useChartPalette } from '../utils/chartTheme'
import {
  monthlyBestPrLineData,
  peakPerformanceForecastChart,
  sixMonthRollingPeakTotalLine,
} from '../utils/trainingCharts'

let chartJsRegistered = false

/** Call before any Chart.js Line render (safe to call multiple times). */
export function ensureAthleteTrainingChartsRegistered() {
  if (chartJsRegistered) return
  ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)
  chartJsRegistered = true
}

ensureAthleteTrainingChartsRegistered()

const DEFAULT_INTRO =
  'Monthly bests from your PR log (click legend entries to hide or show a lift). The middle chart marks competition-total peaks and a simple rhythm-based next-window estimate; the rolling line is a six-month peak on total. Treat projections as planning hints, not guarantees.'

/**
 * Three PR/total trend charts shared by the athlete stats drawer and the coach
 * program editor. Purely presentational — caller supplies `personalRecords`.
 */
export default function AthleteTrainingTrendCharts({
  personalRecords,
  intro = DEFAULT_INTRO,
  className = '',
  /** 'coach' swaps empty-state copy to third-person (read-only roster view). */
  audience = 'athlete',
}) {
  const isCoach = audience === 'coach'
  const chartPalette = useChartPalette()

  const prHistoryChart = useMemo(
    () => monthlyBestPrLineData(personalRecords, ['snatch', 'clean_jerk', 'total'], chartPalette),
    [personalRecords, chartPalette],
  )

  const peakForecast = useMemo(
    () => peakPerformanceForecastChart(personalRecords, chartPalette),
    [personalRecords, chartPalette],
  )

  const rollingPeakChart = useMemo(
    () => sixMonthRollingPeakTotalLine(personalRecords, chartPalette),
    [personalRecords, chartPalette],
  )

  const sharedChartOptions = useMemo(
    () => buildChartJsCommonOptions(chartPalette),
    [chartPalette],
  )

  return (
    <div className={className}>
      {intro ? <p className="athlete-charts-intro">{intro}</p> : null}
      <div className="athlete-drawer-stats-grid athlete-drawer-stats-grid--three">
        <div className="chart-card">
          <h4>PR trend (monthly best)</h4>
          {personalRecords.length === 0 ? (
            <div className="chart-empty">
              {isCoach ? 'No PRs logged for this athlete yet.' : 'Log a PR to see your trend.'}
            </div>
          ) : (
            <Line data={prHistoryChart} options={sharedChartOptions} />
          )}
        </div>
        <div className="chart-card">
          <h4>Peak rhythm &amp; forecast</h4>
          {peakForecast.labels.length === 0 ? (
            <div className="chart-empty">
              {isCoach
                ? 'No competition totals yet — peak timing and forecast appear after they log totals across months.'
                : 'Log a competition total to see peak timing and a forecast.'}
            </div>
          ) : (
            <>
              <Line data={{ labels: peakForecast.labels, datasets: peakForecast.datasets }} options={sharedChartOptions} />
              {peakForecast.insights.length > 0 && (
                <ul className="athlete-chart-footnote" aria-label="Chart notes">
                  {peakForecast.insights.map((text, i) => (
                    <li key={`${i}-${text.slice(0, 48)}`}>{text}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <div className="chart-card">
          <h4>Rolling strength trend</h4>
          {personalRecords.filter((r) => r.lift_type === 'total').length === 0 ? (
            <div className="chart-empty">
              {isCoach ? 'No total PRs yet — rolling peak needs at least one competition total.' : 'Log a total PR to see the rolling peak line.'}
            </div>
          ) : (
            <Line data={rollingPeakChart} options={sharedChartOptions} />
          )}
        </div>
      </div>
    </div>
  )
}
