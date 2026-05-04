import { describe, expect, it } from 'vitest'
import { CHART_PALETTE_FALLBACK, readChartPaletteFromCss } from '../utils/chartTheme'

describe('chartTheme', () => {
  it('fallback palette has all series keys', () => {
    expect(CHART_PALETTE_FALLBACK.snBorder).toBeTruthy()
    expect(CHART_PALETTE_FALLBACK.legend).toBeTruthy()
  })

  it('readChartPaletteFromCss returns a full object in jsdom', () => {
    const p = readChartPaletteFromCss()
    expect(p.grid).toBeTruthy()
    expect(p.tooltipBg).toBeTruthy()
  })
})
