import { useEffect, useMemo, useRef, useState } from 'react'
import { BLOCK_PRESETS } from '../utils/blockLength'
import { PROGRAM_TEMPLATE_WEB_SPREADSHEET_PALETTE } from '../utils/programTemplate'
import { createRestExercise } from '../utils/restTemplate'

// Columns match the xlsx template schema 1:1 so what coaches see here is what
// they'd see in Excel. Each row = one exercise on one day.
const ALL_COLUMNS = [
  { key: 'week', label: 'Week', width: '4rem' },
  { key: 'name', label: 'Exercise', width: '14rem' },
  { key: 'sets', label: 'Sets', width: '4rem' },
  { key: 'reps', label: 'Reps', width: '6rem' },
  { key: 'percent_1rm', label: '% 1RM', width: '5rem' },
  { key: 'rpe', label: 'RPE', width: '4rem' },
  { key: 'weight', label: 'Weight', width: '6rem' },
  { key: 'tempo', label: 'Tempo', width: '6rem' },
  { key: 'rest', label: 'Rest', width: '5rem' },
  { key: 'notes', label: 'Notes', width: '16rem' },
]

// Match the Card View behavior: when an intensity mode is chosen, hide the
// other two intensity columns. Hidden cells keep their data (only the coach's
// display preference filters), so switching modes never loses input.
const columnsForMode = (mode) => {
  const hide = new Set()
  if (mode === 'percent_1rm') { hide.add('rpe'); hide.add('weight') }
  if (mode === 'rpe')         { hide.add('percent_1rm'); hide.add('weight') }
  if (mode === 'weight')      { hide.add('percent_1rm'); hide.add('rpe') }
  return ALL_COLUMNS.filter((c) => !hide.has(c.key))
}

const EMPTY_ROW_PAD = 3 // always render this many blank rows at the bottom for quick entry
const MIN_ROWS_PER_WEEK = 5
const BLANK_ROW = {
  week: '', day: '', name: '', sets: '', reps: '',
  percent_1rm: '', rpe: '', weight: '', tempo: '', rest: '', notes: '',
}
const DAY_OPTIONS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const _norm = (s) => String(s || '').trim().toLowerCase()
const BLOCK_WEEKS_BY_KEY = { '4wk': 4, '8wk': 8, '16wk': 16 }
const PLACEHOLDER_BY_COL = {
  name: 'Enter exercise',
  sets: 'Enter sets',
  reps: 'Enter reps',
  percent_1rm: 'Enter %',
  rpe: 'Enter RPE',
  weight: 'Enter weight',
  tempo: 'Enter tempo',
  rest: 'Enter rest',
  notes: 'Enter notes',
}
const _weekSortValue = (value) => {
  const n = Number.parseInt(String(value || '').trim(), 10)
  return Number.isFinite(n) && n > 0 ? n : Number.POSITIVE_INFINITY
}
const _maxWeekInRows = (rows) => {
  let max = 1
  for (const row of (rows || [])) {
    const n = Number.parseInt(String(row?.week ?? '').trim(), 10)
    if (Number.isFinite(n) && n > max) max = n
  }
  return max
}

const programDataToRowsForDay = (programData, activeDay) => {
  const days = Array.isArray(programData?.days) ? programData.days : []
  const hit = days.find((d) => _norm(d.day) === _norm(activeDay))
  const exercises = Array.isArray(hit?.exercises) ? hit.exercises : []
  const rows = exercises.map((exercise) => ({
    week: exercise.week || '',
    day: activeDay,
    name: exercise.name || '',
    sets: exercise.sets || '',
    reps: exercise.reps || '',
    percent_1rm: exercise.percent_1rm || '',
    rpe: exercise.rpe || '',
    weight: exercise.weight || '',
    tempo: exercise.tempo || '',
    rest: exercise.rest || '',
    notes: exercise.notes || '',
  }))
  // Keep each day section grouped by week number 1..n for predictable editing.
  rows.sort((a, b) => _weekSortValue(a.week) - _weekSortValue(b.week))
  return rows
}

const rowsToProgramDataForDay = (programData, dayName, dayRows, weekStartDate) => {
  const days = Array.isArray(programData?.days) ? [...programData.days] : []
  const dayIndex = days.findIndex((d) => _norm(d.day) === _norm(dayName))
  const exercises = dayRows
    .filter((row) => String(row.name || '').trim())
    .map((row) => {
      const percent = String(row.percent_1rm ?? '').trim()
      const rpe = String(row.rpe ?? '').trim()
      const weight = String(row.weight ?? '').trim()
      return {
        name: String(row.name ?? '').trim(),
        sets: String(row.sets ?? '').trim(),
        reps: String(row.reps ?? '').trim(),
        percent_1rm: percent,
        rpe,
        weight,
        tempo: String(row.tempo ?? '').trim(),
        rest: String(row.rest ?? '').trim(),
        intensity: percent || rpe || weight,
        notes: String(row.notes ?? '').trim(),
        week: String(row.week ?? '').trim(),
      }
    })
  exercises.sort((a, b) => _weekSortValue(a.week) - _weekSortValue(b.week))
  if (dayIndex >= 0) {
    days[dayIndex] = { ...days[dayIndex], day: dayName, exercises }
  } else {
    days.push({ day: dayName, exercises })
  }
  return {
    ...programData,
    week_start_date: weekStartDate || new Date().toISOString().split('T')[0],
    days,
  }
}

const SpreadsheetEditor = ({
  programData,
  onChange,
  intensityMode = 'percent_1rm',
  blockPresetKey = 'custom',
  weekCount,
  onAddCustomWeek,
  onRemoveCustomWeek,
  onBlockPresetSelect,
  onBlockCustomSelect,
}) => {
  const weekStartDate = programData?.week_start_date
  const [activeDay, setActiveDay] = useState('Monday')
  const parsedWeekCount = Number.parseInt(String(weekCount ?? ''), 10)
  const explicitWeekCount = Number.isFinite(parsedWeekCount) && parsedWeekCount > 0 ? parsedWeekCount : null
  const blockWeeks = useMemo(
    () => {
      // Presets always keep their fixed week size (4/8/16). Custom defaults to
      // 4 only when no explicit count exists; once explicit, honor 1..n exactly.
      if (blockPresetKey === 'custom') return explicitWeekCount || 4
      return Math.max(BLOCK_WEEKS_BY_KEY[blockPresetKey] || 4, explicitWeekCount || 0, 4)
    },
    [blockPresetKey, explicitWeekCount],
  )
  const baseRows = useMemo(() => programDataToRowsForDay(programData, activeDay), [programData, activeDay])
  const columns = useMemo(() => columnsForMode(intensityMode), [intensityMode])
  const [draftRows, setDraftRows] = useState({})
  const dayCounts = useMemo(() => {
    const days = Array.isArray(programData?.days) ? programData.days : []
    const map = {}
    for (const day of DAY_OPTIONS) map[day] = 0
    for (const d of days) {
      const key = DAY_OPTIONS.find((k) => _norm(k) === _norm(d.day))
      if (!key) continue
      map[key] = Array.isArray(d.exercises) ? d.exercises.length : 0
    }
    return map
  }, [programData])
  const paletteVars = useMemo(
    () => ({
      '--st-header-bg': PROGRAM_TEMPLATE_WEB_SPREADSHEET_PALETTE.headerBackground,
      '--st-header-text': PROGRAM_TEMPLATE_WEB_SPREADSHEET_PALETTE.headerText,
      '--st-header-border': PROGRAM_TEMPLATE_WEB_SPREADSHEET_PALETTE.headerBorder,
      '--st-pad-bg': 'rgba(243, 246, 250, 0.07)',
    }),
    [],
  )

  // Always show a buffer of empty rows for quick entry. They get filtered out
  // on serialize so they never corrupt the program_data shape.
  const displayRows = useMemo(() => {
    const padded = [...baseRows]
    const minTemplateRows = blockWeeks * MIN_ROWS_PER_WEEK
    const templateFloor = Math.max(minTemplateRows, baseRows.length + EMPTY_ROW_PAD)
    while (padded.length < templateFloor) {
      const rowIndex = padded.length
      const week = String(Math.floor(rowIndex / MIN_ROWS_PER_WEEK) + 1)
      padded.push({ ...BLANK_ROW, day: activeDay, week })
    }
    for (const [indexText, draft] of Object.entries(draftRows)) {
      const index = Number(indexText)
      if (Number.isNaN(index)) continue
      while (padded.length <= index) padded.push({ ...BLANK_ROW })
      padded[index] = { ...padded[index], ...draft }
    }
    return padded
  }, [activeDay, baseRows, blockWeeks, draftRows])
  const firstHintRowIndex = useMemo(
    () => displayRows.findIndex((row) => !String(row.name || '').trim()),
    [displayRows],
  )

  useEffect(() => {
    setDraftRows((current) => {
      const next = {}
      let changed = false
      for (const [indexText, draft] of Object.entries(current)) {
        const index = Number(indexText)
        if (Number.isNaN(index)) {
          changed = true
          continue
        }
        next[indexText] = draft
      }
      return changed ? next : current
    })
  }, [baseRows.length])

  useEffect(() => {
    setDraftRows({})
  }, [activeDay])

  const tableRef = useRef(null)

  const handleCellChange = (rowIndex, columnKey, value) => {
    if (rowIndex < baseRows.length) {
      const next = displayRows.map((row, i) =>
        i === rowIndex ? { ...row, [columnKey]: value } : row
      )
      onChange(rowsToProgramDataForDay(programData, activeDay, next, weekStartDate))
      return
    }
    setDraftRows((current) => ({
      ...current,
      [rowIndex]: { ...displayRows[rowIndex], day: activeDay, [columnKey]: value },
    }))
  }

  const commitRow = (rowIndex) => {
    const draftRow = draftRows[rowIndex] || displayRows[rowIndex]
    if (!draftRow) return false
    const isPadRow = rowIndex >= baseRows.length
    const hasDay = String(draftRow.day || '').trim().length > 0
    const hasExerciseName = String(draftRow.name || '').trim().length > 0
    if (isPadRow && (!hasDay || !hasExerciseName)) return false

    const serialRows = displayRows.map((row, idx) => {
      const r = idx === rowIndex ? { ...row, ...draftRow } : row
      if (idx < baseRows.length) return r
      const rowHasDay = String(r.day || '').trim().length > 0
      const rowHasExerciseName = String(r.name || '').trim().length > 0
      return rowHasDay && rowHasExerciseName ? r : { ...BLANK_ROW }
    })
    onChange(rowsToProgramDataForDay(programData, activeDay, serialRows, weekStartDate))
    setDraftRows((current) => {
      const next = { ...current }
      delete next[rowIndex]
      return next
    })
    return true
  }

  const handleCellBlur = () => {
    // Explicit-commit UX: blur never commits. Enter commits the row.
  }
  const applyRestDay = () => {
    const targetWeeks = Math.max(blockWeeks, _maxWeekInRows(baseRows))
    const rowsPerWeek = MIN_ROWS_PER_WEEK
    const totalRows = targetWeeks * rowsPerWeek
    const restRows = Array.from({ length: totalRows }).map((_, idx) => {
      const week = Math.floor(idx / rowsPerWeek) + 1
      return {
        ...BLANK_ROW,
        ...createRestExercise(week),
        day: activeDay,
      }
    })
    onChange(rowsToProgramDataForDay(programData, activeDay, restRows, weekStartDate))
    setDraftRows({})
  }

  // Arrow/enter navigation to move between cells like Excel.
  const handleKeyDown = (event, rowIndex, columnIndex) => {
    const key = event.key
    const shouldMove = ['ArrowUp', 'ArrowDown', 'Enter', 'Tab'].includes(key)
    if (!shouldMove) return
    let targetRow = rowIndex
    let targetCol = columnIndex
    if (key === 'ArrowUp') targetRow -= 1
    else if (key === 'ArrowDown') targetRow += 1
    else if (key === 'Enter') {
      event.preventDefault()
      if (!commitRow(rowIndex)) return
      targetRow += 1
    }
    else if (key === 'Tab') {
      event.preventDefault()
      targetCol = event.shiftKey ? columnIndex - 1 : columnIndex + 1
      if (targetCol < 0) {
        targetCol = columns.length - 1
        targetRow -= 1
      } else if (targetCol >= columns.length) {
        targetCol = 0
        targetRow += 1
      }
    }
    const inputs = tableRef.current?.querySelectorAll('[data-cell]')
    if (!inputs) return
    const targetIndex = targetRow * columns.length + targetCol
    const nextInput = inputs[targetIndex]
    if (nextInput) {
      event.preventDefault()
      nextInput.focus()
      nextInput.select?.()
    }
  }

  return (
    <div className="spreadsheet-editor section-card" style={paletteVars}>
      {typeof onBlockPresetSelect === 'function' && (
        <div className="spreadsheet-template-block-row">
          <span className="spreadsheet-template-block-label">Block length</span>
          <div className="block-length-options" role="radiogroup" aria-label="Block length matching Excel template tabs">
            {BLOCK_PRESETS.map((preset) => (
              <button
                key={preset.key}
                type="button"
                role="radio"
                aria-checked={blockPresetKey === preset.key}
                className={`block-length-chip ${blockPresetKey === preset.key ? 'is-active' : ''}`}
                onClick={() => onBlockPresetSelect(preset.weeks)}
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              role="radio"
              aria-checked={blockPresetKey === 'custom'}
              className={`block-length-chip block-length-chip-custom ${blockPresetKey === 'custom' ? 'is-active' : ''}`}
              onClick={() => onBlockCustomSelect?.()}
            >
              Custom
            </button>
          </div>
        </div>
      )}
      {blockPresetKey === 'custom' && (
        <div className="spreadsheet-week-controls" aria-label="Custom week controls">
          <span className="spreadsheet-week-counter">
            Week count: <strong>{Math.max(1, Number(weekCount) || 1)}</strong>
          </span>
          <button type="button" className="text-btn" onClick={onAddCustomWeek}>
            + Add week
          </button>
          <button
            type="button"
            className="text-btn"
            onClick={onRemoveCustomWeek}
            disabled={(Number(weekCount) || 1) <= 1}
          >
            − Remove week
          </button>
        </div>
      )}
      <div className="spreadsheet-editor-instructions" role="note" aria-label="Spreadsheet row instructions">
        <div className="spreadsheet-editor-instructions-title">
          <span className="spreadsheet-editor-instructions-icon" aria-hidden="true">ⓘ</span>
          <span>How to add a row</span>
        </div>
        <ul>
          <li>Select a day.</li>
          <li>Enter exercise and any details.</li>
          <li>When the row is complete, press Enter to add it.</li>
        </ul>
      </div>
      <div className="spreadsheet-editor-hint section-subtitle">
        Same columns as the downloaded Excel (4 / 8 / 16 Week template). Editing day: {activeDay}.
      </div>
      <div className="spreadsheet-day-tabs" role="tablist" aria-label="Training day tabs">
        {DAY_OPTIONS.map((day) => (
          <button
            key={day}
            type="button"
            role="tab"
            aria-selected={activeDay === day}
            className={`spreadsheet-day-tab ${activeDay === day ? 'is-active' : ''}`}
            onClick={() => setActiveDay(day)}
          >
            {day}
            <span className="spreadsheet-day-tab-count">{dayCounts[day] || 0}</span>
          </button>
        ))}
      </div>
      <div className="spreadsheet-day-actions">
        <button type="button" className="text-btn spreadsheet-rest-btn" onClick={applyRestDay}>
          Set Rest Day
        </button>
      </div>
      <div className="spreadsheet-editor-scroll">
        <table ref={tableRef} className="spreadsheet-editor-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} style={{ width: col.width }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, rowIndex) => {
              // Group rows by day: the first row of a day-run keeps its label
              // visible and gets a top-border accent; subsequent rows blank
              // their day label via CSS. The underlying input stays editable
              // (focus reveals the value) so keyboard nav and editing are
              // unaffected. Serialization treats each row independently.
              const prevDay = rowIndex > 0 ? displayRows[rowIndex - 1].day : null
              const currentDay = row.day || ''
              const isDayRepeat = !!currentDay && currentDay === prevDay
              const isDayStart = !!currentDay && !isDayRepeat
              const isPadRow = rowIndex >= baseRows.length
              const prevWeek = rowIndex > 0 ? String(displayRows[rowIndex - 1].week || '').trim() : ''
              const currentWeek = String(row.week || '').trim()
              const isWeekStart = !!currentWeek && currentWeek !== prevWeek
              return (
                <tr
                  key={rowIndex}
                  className={`${isDayStart ? 'is-day-start' : ''} ${isDayRepeat ? 'is-day-repeat-row' : ''} ${isPadRow ? 'is-pad-row' : ''} ${isWeekStart ? 'is-week-start' : ''}`.trim()}
                >
                  {columns.map((col, columnIndex) => (
                    <td key={col.key} className={col.key === 'day' && isDayRepeat ? 'is-day-repeat' : ''}>
                      {col.key === 'day' ? (
                        <select
                          data-cell
                          data-row-index={rowIndex}
                          value={row.day ?? ''}
                          onChange={(event) => handleCellChange(rowIndex, 'day', event.target.value)}
                          onBlur={(event) => handleCellBlur(rowIndex, event)}
                          onKeyDown={(event) => handleKeyDown(event, rowIndex, columnIndex)}
                          aria-label={`Day row ${rowIndex + 1}`}
                        >
                          <option value="">Select day</option>
                          {DAY_OPTIONS.map((dayOption) => (
                            <option key={dayOption} value={dayOption}>{dayOption}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          data-cell
                          data-row-index={rowIndex}
                          type="text"
                          value={row[col.key] ?? ''}
                          placeholder={rowIndex === firstHintRowIndex ? PLACEHOLDER_BY_COL[col.key] || '' : ''}
                          onChange={(event) => handleCellChange(rowIndex, col.key, event.target.value)}
                          onBlur={(event) => handleCellBlur(rowIndex, event)}
                          onKeyDown={(event) => handleKeyDown(event, rowIndex, columnIndex)}
                        />
                      )}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default SpreadsheetEditor
