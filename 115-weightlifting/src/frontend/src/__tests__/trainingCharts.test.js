import { describe, expect, it } from 'vitest'
import {
  monthlyBestPrLineData,
  peakPerformanceForecastChart,
  rosterAverageMonthlyBestPrLineData,
  rosterAverageRollingPeakTotalLine,
  sixMonthRollingPeakTotalLine,
} from '../utils/trainingCharts'

describe('trainingCharts', () => {
  const sample = [
    { date: '2024-01-10', lift_type: 'snatch', weight: '100' },
    { date: '2024-01-20', lift_type: 'snatch', weight: '102' },
    { date: '2024-01-15', lift_type: 'clean_jerk', weight: '125' },
    { date: '2024-01-25', lift_type: 'clean_jerk', weight: '128' },
    { date: '2024-01-22', lift_type: 'total', weight: '228' },
    { date: '2024-04-05', lift_type: 'total', weight: '235' },
    { date: '2024-04-01', lift_type: 'snatch', weight: '105' },
    { date: '2024-04-02', lift_type: 'clean_jerk', weight: '130' },
  ]

  it('monthlyBestPrLineData picks monthly maxima', () => {
    const { labels, datasets } = monthlyBestPrLineData(sample)
    expect(labels).toEqual(['2024-01', '2024-04'])
    const sn = datasets.find((d) => d.label === 'Snatch')
    expect(sn.data).toEqual([102, 105])
  })

  it('peakPerformanceForecastChart builds monthly totals and optional forecast', () => {
    const { labels, datasets, insights } = peakPerformanceForecastChart(sample)
    expect(labels).toContain('2024-01')
    expect(labels).toContain('2024-04')
    const monthly = datasets.find((d) => d.label.includes('Monthly'))
    expect(monthly).toBeTruthy()
    expect(monthly.fill).toBe(true)
    const apr = labels.indexOf('2024-04')
    expect(monthly.data[apr]).toBe(235)
    expect(datasets.length).toBeGreaterThanOrEqual(1)
    expect(insights.length).toBeGreaterThan(0)
  })

  it('peakPerformanceForecastChart omits dashed forecast until two peaks exist', () => {
    const oneMonth = [{ date: '2024-05-01', lift_type: 'total', weight: '200' }]
    const { datasets, insights } = peakPerformanceForecastChart(oneMonth)
    expect(datasets.length).toBe(1)
    expect(insights[0]).toMatch(/more months/i)
  })

  it('sixMonthRollingPeakTotalLine returns a filled month range', () => {
    const { labels, datasets } = sixMonthRollingPeakTotalLine(sample)
    expect(labels.length).toBeGreaterThanOrEqual(4)
    expect(datasets[0].data.every((v) => v == null || typeof v === 'number')).toBe(true)
  })

  it('rosterAverageMonthlyBestPrLineData averages athletes per month', () => {
    const a1 = [
      { date: '2024-01-10', lift_type: 'snatch', weight: '100' },
      { date: '2024-01-20', lift_type: 'snatch', weight: '102' },
    ]
    const a2 = [
      { date: '2024-01-05', lift_type: 'snatch', weight: '110' },
    ]
    const { labels, datasets } = rosterAverageMonthlyBestPrLineData([a1, a2])
    expect(labels).toContain('2024-01')
    const sn = datasets.find((d) => d.label.includes('Snatch'))
    const idx = labels.indexOf('2024-01')
    expect(sn.data[idx]).toBe(106)
  })

  it('rosterAverageRollingPeakTotalLine averages rolling totals', () => {
    const t1 = [{ date: '2024-01-10', lift_type: 'total', weight: '200' }]
    const t2 = [{ date: '2024-01-12', lift_type: 'total', weight: '220' }]
    const { labels, datasets } = rosterAverageRollingPeakTotalLine([t1, t2])
    expect(labels.length).toBeGreaterThan(0)
    const jan = labels.indexOf('2024-01')
    expect(datasets[0].data[jan]).toBe(210)
  })
})
