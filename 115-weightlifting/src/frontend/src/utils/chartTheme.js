import { useEffect, useMemo, useState } from 'react'

/** Fallback when CSS variables are missing (tests / first paint). */
export const CHART_PALETTE_FALLBACK = {
  axisTick: '#b3d4ee',
  grid: 'rgba(95, 228, 255, 0.14)',
  border: 'rgba(95, 228, 255, 0.34)',
  snBorder: '#5fe4ff',
  snFill: 'rgba(95, 228, 255, 0.14)',
  snPoint: '#a5ecff',
  cjBorder: '#36f0c5',
  cjFill: 'rgba(54, 240, 197, 0.14)',
  cjPoint: '#7ff7dd',
  totBorder: '#ffb23f',
  totFill: 'rgba(255, 178, 63, 0.14)',
  totPoint: '#ffd489',
  monthlyTotalLine: 'rgba(165, 236, 255, 0.55)',
  monthlyTotalFill: 'rgba(95, 228, 255, 0.08)',
  peakMarker: '#ffb23f',
  forecastLine: 'rgba(54, 240, 197, 0.85)',
  forecastPoint: '#36f0c5',
  rollingBorder: '#36f0c5',
  rollingFill: 'rgba(54, 240, 197, 0.12)',
  rollingPoint: '#7ff7dd',
  tooltipBg: 'rgba(4, 10, 20, 0.96)',
  tooltipTitle: '#f4f7fb',
  tooltipBody: '#c9d6e3',
  tooltipBorder: 'rgba(95, 228, 255, 0.28)',
  legend: '#f4f7fb',
}

const KEYS = [
  ['axisTick', '--chart-axis-tick'],
  ['grid', '--chart-grid'],
  ['border', '--chart-border'],
  ['snBorder', '--chart-sn-border'],
  ['snFill', '--chart-sn-fill'],
  ['snPoint', '--chart-sn-point'],
  ['cjBorder', '--chart-cj-border'],
  ['cjFill', '--chart-cj-fill'],
  ['cjPoint', '--chart-cj-point'],
  ['totBorder', '--chart-tot-border'],
  ['totFill', '--chart-tot-fill'],
  ['totPoint', '--chart-tot-point'],
  ['monthlyTotalLine', '--chart-monthly-total-line'],
  ['monthlyTotalFill', '--chart-monthly-total-fill'],
  ['peakMarker', '--chart-peak-marker'],
  ['forecastLine', '--chart-forecast-line'],
  ['forecastPoint', '--chart-forecast-point'],
  ['rollingBorder', '--chart-rolling-border'],
  ['rollingFill', '--chart-rolling-fill'],
  ['rollingPoint', '--chart-rolling-point'],
  ['tooltipBg', '--chart-tooltip-bg'],
  ['tooltipTitle', '--chart-tooltip-title'],
  ['tooltipBody', '--chart-tooltip-body'],
  ['tooltipBorder', '--chart-tooltip-border'],
  ['legend', '--chart-legend'],
]

export function readChartPaletteFromCss() {
  if (typeof document === 'undefined') return { ...CHART_PALETTE_FALLBACK }
  const cs = getComputedStyle(document.documentElement)
  const out = { ...CHART_PALETTE_FALLBACK }
  for (const [prop, cssName] of KEYS) {
    const raw = cs.getPropertyValue(cssName).trim()
    if (raw) out[prop] = raw
  }
  return out
}

export function useChartPalette() {
  const [rev, setRev] = useState(0)
  useEffect(() => {
    const bump = () => setRev((n) => n + 1)
    bump()
    const mo = new MutationObserver(bump)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => mo.disconnect()
  }, [])
  return useMemo(() => readChartPaletteFromCss(), [rev])
}

export function buildChartJsCommonOptions(palette) {
  const p = palette || CHART_PALETTE_FALLBACK
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: p.legend,
          usePointStyle: true,
          boxWidth: 10,
          padding: 14,
          font: { size: 11, family: 'Inter, sans-serif' },
        },
      },
      tooltip: {
        backgroundColor: p.tooltipBg,
        titleColor: p.tooltipTitle,
        bodyColor: p.tooltipBody,
        borderColor: p.tooltipBorder,
        borderWidth: 1,
        padding: 10,
        cornerRadius: 6,
      },
    },
    scales: {
      x: {
        ticks: {
          color: p.axisTick,
          maxRotation: 40,
          minRotation: 0,
          autoSkip: true,
          maxTicksLimit: 18,
        },
        grid: { color: p.grid },
        border: { color: p.border },
      },
      y: {
        beginAtZero: false,
        ticks: { color: p.axisTick },
        grid: { color: p.grid },
        border: { color: p.border },
      },
    },
  }
}
