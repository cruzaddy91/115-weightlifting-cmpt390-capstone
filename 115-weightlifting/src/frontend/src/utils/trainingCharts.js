/**
 * Pure chart-data builders for athlete PR / total trends (Chart.js-friendly).
 * Keeps AthleteDashboard lean and unit-testable without rendering.
 */

import { CHART_PALETTE_FALLBACK } from './chartTheme'

const LIFT_LABELS = { snatch: 'Snatch', clean_jerk: 'Clean & Jerk', total: 'Total' }

const monthKey = (isoDate) => isoDate.slice(0, 7)

const parseMonthKey = (key) => {
  const [y, m] = key.split('-').map(Number)
  return { y, m }
}

const addMonthsKey = (key, delta) => {
  const { y, m } = parseMonthKey(key)
  let mm = m + delta
  let yy = y
  while (mm > 12) {
    mm -= 12
    yy += 1
  }
  while (mm < 1) {
    mm += 12
    yy -= 1
  }
  return `${yy}-${String(mm).padStart(2, '0')}`
}

/** Monthly best per lift — smooths multi-year PR logs for readable line charts. */
export function monthlyBestPrLineData(
  records,
  liftTypes = ['snatch', 'clean_jerk', 'total'],
  palette = CHART_PALETTE_FALLBACK,
) {
  const byLiftMonth = new Map()
  const months = new Set()
  for (const r of records) {
    if (!liftTypes.includes(r.lift_type)) continue
    const m = monthKey(r.date)
    months.add(m)
    const k = `${r.lift_type}\t${m}`
    const w = Number(r.weight)
    if (Number.isNaN(w)) continue
    const cur = byLiftMonth.get(k)
    if (cur == null || w > cur) byLiftMonth.set(k, w)
  }
  const labels = [...months].sort()
  const colors = [
    { border: palette.snBorder, fill: palette.snFill, point: palette.snPoint },
    { border: palette.cjBorder, fill: palette.cjFill, point: palette.cjPoint },
    { border: palette.totBorder, fill: palette.totFill, point: palette.totPoint },
  ]
  return {
    labels,
    datasets: liftTypes.map((lift, i) => ({
      label: LIFT_LABELS[lift] || lift,
      data: labels.map((lab) => {
        const v = byLiftMonth.get(`${lift}\t${lab}`)
        return v == null ? null : v
      }),
      borderColor: colors[i % colors.length].border,
      backgroundColor: colors[i % colors.length].fill,
      pointBackgroundColor: colors[i % colors.length].point,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.32,
      spanGaps: true,
    })),
  }
}

function _monthlyMaxTotalsSeries(records) {
  const totals = records
    .filter((r) => r.lift_type === 'total')
    .map((r) => ({ d: r.date, w: Number(r.weight) }))
    .filter((r) => !Number.isNaN(r.w))
    .sort((a, b) => a.d.localeCompare(b.d))
  if (totals.length === 0) return { labels: [], values: [] }

  const monthKeys = totals.map((r) => monthKey(r.d))
  let cur = monthKeys.reduce((a, b) => (a < b ? a : b))
  const end = monthKeys.reduce((a, b) => (a > b ? a : b))
  const labels = []
  while (cur <= end) {
    labels.push(cur)
    cur = addMonthsKey(cur, 1)
  }
  const maxInMonth = (mk) => {
    let m = -Infinity
    for (const r of totals) {
      if (monthKey(r.d) === mk && r.w > m) m = r.w
    }
    return m
  }
  const values = labels.map((mk) => {
    const v = maxInMonth(mk)
    return v === -Infinity ? null : Math.round(v * 10) / 10
  })
  return { labels, values }
}

function _detectPeakIndices(values, radius = 2, prominenceKg = 1.5) {
  const peaks = []
  for (let i = 0; i < values.length; i += 1) {
    const v = values[i]
    if (v == null || !Number.isFinite(v)) continue
    let higherNeighbor = false
    for (let j = i - radius; j <= i + radius; j += 1) {
      if (j < 0 || j >= values.length || j === i) continue
      const w = values[j]
      if (w != null && Number.isFinite(w) && w > v) {
        higherNeighbor = true
        break
      }
    }
    if (higherNeighbor) continue
    let sum = 0
    let n = 0
    for (let j = i - radius; j <= i + radius; j += 1) {
      if (j < 0 || j >= values.length || j === i) continue
      const w = values[j]
      if (w != null && Number.isFinite(w)) {
        sum += w
        n += 1
      }
    }
    if (n > 0 && v < sum / n + prominenceKg) continue
    peaks.push(i)
  }
  const sorted = [...new Set(peaks)].sort((a, b) => a - b)
  const deduped = []
  for (const idx of sorted) {
    if (deduped.length && idx - deduped[deduped.length - 1] <= 1) {
      const prev = deduped[deduped.length - 1]
      if ((values[idx] ?? 0) >= (values[prev] ?? 0)) deduped[deduped.length - 1] = idx
    } else {
      deduped.push(idx)
    }
  }
  return deduped
}

function _linRegSlopeIntercept(points) {
  const n = points.length
  if (n < 2) return { slope: 0, intercept: points[0]?.y ?? 0 }
  const mx = points.reduce((s, p) => s + p.x, 0) / n
  const my = points.reduce((s, p) => s + p.y, 0) / n
  let num = 0
  let den = 0
  for (const p of points) {
    num += (p.x - mx) * (p.y - my)
    den += (p.x - mx) ** 2
  }
  const slope = den > 1e-9 ? num / den : 0
  const intercept = my - slope * mx
  return { slope, intercept }
}

/**
 * Monthly competition-total bests, local maxima highlighted as peaks, and a
 * cadence + regression estimate for the next high window. Block names are not
 * stored on PRs — copy nudges the athlete + coach to map peaks to their program.
 */
export function peakPerformanceForecastChart(records, palette = CHART_PALETTE_FALLBACK) {
  const { labels: baseLabels, values: baseValues } = _monthlyMaxTotalsSeries(records)
  if (baseLabels.length === 0) {
    return { labels: [], datasets: [], insights: [] }
  }

  const labels = [...baseLabels]
  const values = [...baseValues]

  const peakIndices = _detectPeakIndices(values)
  const peakSet = new Set(peakIndices)

  const insights = []
  let forecastData = labels.map(() => null)

  if (peakIndices.length < 2) {
    insights.push(
      'Log competition totals across more months so peak spacing and a next-window estimate can appear.',
    )
  } else {
    const gaps = []
    for (let i = 1; i < peakIndices.length; i += 1) {
      gaps.push(peakIndices[i] - peakIndices[i - 1])
    }
    const recent = gaps.slice(-3)
    const avgGapMonths = recent.reduce((a, b) => a + b, 0) / recent.length
    const gapWeeks = Math.round(avgGapMonths * 4.345)
    insights.push(
      `Recent peaks sit about ${gapWeeks} weeks apart on average (${avgGapMonths.toFixed(1)} mo). Peaks are usually held only 1–2 weeks — compare this rhythm to your block calendar and meet dates.`,
    )

    const lastPk = peakIndices[peakIndices.length - 1]
    const projIdx = lastPk + Math.max(1, Math.round(avgGapMonths))

    while (labels.length <= projIdx) {
      labels.push(addMonthsKey(labels[labels.length - 1], 1))
      values.push(null)
    }

    const pts = peakIndices.slice(-4).map((i) => ({ x: i, y: values[i] }))
    const { slope, intercept } = _linRegSlopeIntercept(pts)
    let projY = slope * projIdx + intercept
    const lastKg = values[lastPk] ?? 0
    if (!Number.isFinite(projY) || projY < lastKg * 0.94) projY = lastKg * 0.995
    if (projY > lastKg * 1.06) projY = lastKg * 1.02
    projY = Math.round(Math.max(40, projY) * 10) / 10

    forecastData = labels.map((_, i) => {
      if (i === lastPk) return values[lastPk]
      if (i === projIdx) return projY
      return null
    })

    insights.push(
      `Estimated next high window around ${labels[projIdx]} (~${projY} kg). Plan a taper to finish 1–2 weeks before a target meet if this lines up.`,
    )
    insights.push(
      'Program block names are not on PR rows — tag meets in notes or compare this curve with your coach’s block sheet to see which phases set up the biggest jumps.',
    )
  }

  const pointRadii = labels.map((_, i) => (peakSet.has(i) ? 11 : 3))
  const pointColors = labels.map((_, i) => (peakSet.has(i) ? palette.peakMarker : palette.totPoint))

  const datasets = [
    {
      label: 'Monthly best total (kg)',
      data: values,
      borderColor: palette.monthlyTotalLine,
      backgroundColor: palette.monthlyTotalFill,
      borderWidth: 2,
      fill: true,
      tension: 0.28,
      pointRadius: pointRadii,
      pointHoverRadius: labels.map((_, i) => (peakSet.has(i) ? 14 : 5)),
      pointBackgroundColor: pointColors,
      spanGaps: true,
    },
  ]

  if (peakIndices.length >= 2) {
    datasets.push({
      label: 'Next peak (estimate)',
      data: forecastData,
      borderColor: palette.forecastLine,
      backgroundColor: 'transparent',
      fill: false,
      borderWidth: 2,
      borderDash: [7, 5],
      pointRadius: labels.map((_, i) => (forecastData[i] != null ? 5 : 0)),
      pointBackgroundColor: labels.map((_, i) => (forecastData[i] != null ? palette.forecastPoint : 'transparent')),
      tension: 0.2,
      spanGaps: true,
    })
  }

  return { labels, datasets, insights }
}

/**
 * Line: rolling 6-calendar-month peak competition total (month-end series).
 * Highlights long-horizon strength trend separate from noisy meet-day totals.
 */
export function sixMonthRollingPeakTotalLine(records, palette = CHART_PALETTE_FALLBACK) {
  const totals = records
    .filter((r) => r.lift_type === 'total')
    .map((r) => ({ d: r.date, w: Number(r.weight) }))
    .filter((r) => !Number.isNaN(r.w))
    .sort((a, b) => a.d.localeCompare(b.d))

  if (totals.length === 0) {
    return { labels: [], datasets: [] }
  }

  const monthKeys = totals.map((r) => monthKey(r.d))
  let cur = monthKeys.reduce((a, b) => (a < b ? a : b))
  const end = monthKeys.reduce((a, b) => (a > b ? a : b))
  const labels = []
  while (cur <= end) {
    labels.push(cur)
    cur = addMonthsKey(cur, 1)
  }

  const maxInMonth = (mk) => {
    let m = -Infinity
    for (const r of totals) {
      if (monthKey(r.d) === mk && r.w > m) m = r.w
    }
    return m
  }

  const data = labels.map((endKey) => {
    let peak = -Infinity
    for (let back = 0; back < 6; back += 1) {
      const mk = addMonthsKey(endKey, -back)
      const v = maxInMonth(mk)
      if (v > peak) peak = v
    }
    return peak === -Infinity ? null : Math.round(peak * 10) / 10
  })

  return {
    labels,
    datasets: [{
      label: '6-mo rolling peak total (kg)',
      data,
      borderColor: palette.rollingBorder,
      backgroundColor: palette.rollingFill,
      pointBackgroundColor: palette.rollingPoint,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.35,
      fill: true,
      spanGaps: true,
    }],
  }
}

/**
 * Mean of each athlete's monthly-best series (per lift), aligned on the union
 * of calendar months. Only athletes with a finite value in that month count
 * toward the average for that point.
 */
export function rosterAverageMonthlyBestPrLineData(
  recordsPerAthlete,
  liftTypes = ['snatch', 'clean_jerk', 'total'],
  palette = CHART_PALETTE_FALLBACK,
) {
  const inputs = (recordsPerAthlete || []).filter((recs) => Array.isArray(recs) && recs.length > 0)
  if (inputs.length === 0) {
    return { labels: [], datasets: [] }
  }

  const perAthlete = inputs.map((recs) => monthlyBestPrLineData(recs, liftTypes, palette))
  const labelSet = new Set()
  for (const chart of perAthlete) {
    for (const lab of chart.labels) labelSet.add(lab)
  }
  const labels = [...labelSet].sort()

  const colors = [
    { border: palette.snBorder, fill: palette.snFill, point: palette.snPoint },
    { border: palette.cjBorder, fill: palette.cjFill, point: palette.cjPoint },
    { border: palette.totBorder, fill: palette.totFill, point: palette.totPoint },
  ]

  const datasets = liftTypes.map((lift, i) => {
    const baseName = LIFT_LABELS[lift] || lift
    return {
      label: `Avg ${baseName} (kg)`,
      data: labels.map((lab) => {
        const nums = []
        for (const chart of perAthlete) {
          const ds = chart.datasets[i]
          const idx = chart.labels.indexOf(lab)
          if (idx < 0) continue
          const v = ds.data[idx]
          if (v != null && Number.isFinite(v)) nums.push(v)
        }
        if (nums.length === 0) return null
        return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10
      }),
      borderColor: colors[i % colors.length].border,
      backgroundColor: colors[i % colors.length].fill,
      pointBackgroundColor: colors[i % colors.length].point,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.32,
      spanGaps: true,
    }
  })

  return { labels, datasets }
}

/**
 * Mean of each athlete's six-month rolling peak total on the union of month labels.
 */
export function rosterAverageRollingPeakTotalLine(
  recordsPerAthlete,
  palette = CHART_PALETTE_FALLBACK,
) {
  const inputs = (recordsPerAthlete || []).filter((recs) => Array.isArray(recs) && recs.length > 0)
  if (inputs.length === 0) {
    return { labels: [], datasets: [] }
  }

  const perAthlete = inputs.map((recs) => sixMonthRollingPeakTotalLine(recs, palette))
  if (perAthlete.every((c) => c.labels.length === 0)) {
    return { labels: [], datasets: [] }
  }

  const labelSet = new Set()
  for (const chart of perAthlete) {
    for (const lab of chart.labels) labelSet.add(lab)
  }
  const labels = [...labelSet].sort()

  const data = labels.map((lab) => {
    const nums = []
    for (const chart of perAthlete) {
      const idx = chart.labels.indexOf(lab)
      if (idx < 0) continue
      const v = chart.datasets[0]?.data[idx]
      if (v != null && Number.isFinite(v)) nums.push(v)
    }
    if (nums.length === 0) return null
    return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10
  })

  return {
    labels,
    datasets: [{
      label: 'Avg 6-mo rolling peak total (kg)',
      data,
      borderColor: palette.rollingBorder,
      backgroundColor: palette.rollingFill,
      pointBackgroundColor: palette.rollingPoint,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.35,
      fill: true,
      spanGaps: true,
    }],
  }
}
