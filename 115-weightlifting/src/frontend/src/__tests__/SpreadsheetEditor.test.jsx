import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import SpreadsheetEditor from '../components/SpreadsheetEditor'

const programFixture = {
  week_start_date: '2026-04-21',
  days: [
    {
      day: 'Monday',
      exercises: [
        {
          name: 'Snatch', sets: '5', reps: '2',
          percent_1rm: '75%', rpe: '', weight: '',
          tempo: '3-1-X-1', rest: '2min', notes: '',
          week: '1',
        },
      ],
    },
    {
      day: 'Tuesday',
      exercises: [
        {
          name: 'Clean & Jerk', sets: '5', reps: '1+1',
          percent_1rm: '80%', rpe: '', weight: '',
          tempo: '', rest: '2min', notes: '',
          week: '1',
        },
      ],
    },
  ],
}

describe('SpreadsheetEditor', () => {
  it('renders day tabs Monday through Sunday', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} />)
    const tablist = screen.getByRole('tablist', { name: /training day tabs/i })
    expect(within(tablist).getByRole('tab', { name: /Monday/i })).toBeTruthy()
    expect(within(tablist).getByRole('tab', { name: /Sunday/i })).toBeTruthy()
  })

  it('shows only active-day rows in the grid', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} />)
    expect(screen.getByDisplayValue('Snatch')).toBeTruthy()
    expect(screen.queryByDisplayValue('Clean & Jerk')).toBeNull()
    fireEvent.click(screen.getByRole('tab', { name: /Tuesday/i }))
    expect(screen.getByDisplayValue('Clean & Jerk')).toBeTruthy()
    expect(screen.queryByDisplayValue('Snatch')).toBeNull()
  })

  it('offers 4/8/16 Week block controls when onBlockPresetSelect is passed', () => {
    const onPreset = vi.fn()
    render(
      <SpreadsheetEditor
        programData={programFixture}
        onChange={() => {}}
        blockPresetKey="4wk"
        onBlockPresetSelect={onPreset}
      />,
    )
    const group = screen.getByRole('radiogroup', { name: /matching excel template tabs/i })
    fireEvent.click(within(group).getByRole('radio', { name: '8 Week' }))
    expect(onPreset).toHaveBeenCalledWith(8)
  })

  it('renders one row per exercise with all expanded columns populated', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} />)
    expect(screen.getByDisplayValue('Snatch')).toBeTruthy()
    expect(screen.getByDisplayValue('3-1-X-1')).toBeTruthy()
    expect(screen.getByDisplayValue('2min')).toBeTruthy()
  })

  it('emits updated program_data preserving all expanded fields when a cell changes', () => {
    const onChange = vi.fn()
    render(<SpreadsheetEditor programData={programFixture} onChange={onChange} />)
    const snatchInput = screen.getByDisplayValue('Snatch')
    fireEvent.change(snatchInput, { target: { value: 'Power Snatch' } })

    const nextProgram = onChange.mock.calls.at(-1)[0]
    const firstExercise = nextProgram.days[0].exercises[0]
    expect(firstExercise.name).toBe('Power Snatch')
    expect(firstExercise.percent_1rm).toBe('75%')
    expect(firstExercise.tempo).toBe('3-1-X-1')
    expect(firstExercise.rest).toBe('2min')
    expect(firstExercise.intensity).toBe('75%') // legacy alias populated
  })

  it('keeps partial padding-row edits local until exercise name is provided', () => {
    const onChange = vi.fn()
    render(<SpreadsheetEditor programData={programFixture} onChange={onChange} />)
    const rows = document.querySelectorAll('.spreadsheet-editor-table tbody tr')
    const thirdPadRow = rows[3]
    const padExerciseInput = within(thirdPadRow).getAllByRole('textbox')[1]
    fireEvent.change(padExerciseInput, { target: { value: 'Snatch Pull' } })
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.keyDown(padExerciseInput, { key: 'Enter' })
    const nextProgram = onChange.mock.calls.at(-1)[0]
    const monday = nextProgram.days.find((d) => d.day === 'Monday')
    expect(monday.exercises.map((x) => x.name)).toContain('Snatch Pull')
  })

  it('saves rows under currently active day tab', () => {
    const onChange = vi.fn()
    render(<SpreadsheetEditor programData={programFixture} onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: /Tuesday/i }))
    const rows = document.querySelectorAll('.spreadsheet-editor-table tbody tr')
    const firstPadRow = rows[2]
    const exerciseInput = within(firstPadRow).getAllByRole('textbox')[1]
    fireEvent.change(exerciseInput, { target: { value: 'Power Clean' } })
    fireEvent.keyDown(exerciseInput, { key: 'Enter' })

    const nextProgram = onChange.mock.calls.at(-1)[0]
    const tuesday = nextProgram.days.find((d) => d.day === 'Tuesday')
    expect(tuesday.exercises.map((x) => x.name)).toContain('Power Clean')
  })

  it('stress: long exercise typing in a new row keeps focus and full text', () => {
    const onChange = vi.fn()
    render(<SpreadsheetEditor programData={programFixture} onChange={onChange} />)
    const rows = document.querySelectorAll('.spreadsheet-editor-table tbody tr')
    const firstPadRow = rows[2]

    const exerciseInput = within(firstPadRow).getAllByRole('textbox')[1]
    exerciseInput.focus()
    const phrase = 'Clean Pull from Blocks with 2s Pause @ Knee'
    let typed = ''
    for (const ch of phrase) {
      typed += ch
      fireEvent.change(exerciseInput, { target: { value: typed } })
      expect(document.activeElement).toBe(exerciseInput)
      expect(exerciseInput.value).toBe(typed)
    }

    fireEvent.keyDown(exerciseInput, { key: 'Enter' })
    const nextProgram = onChange.mock.calls.at(-1)[0]
    const monday = nextProgram.days.find((d) => d.day === 'Monday')
    expect(monday.exercises.map((x) => x.name)).toContain(phrase)
  })

  it('does not commit while moving between cells in same row; commits on Enter', () => {
    const onChange = vi.fn()
    render(<SpreadsheetEditor programData={programFixture} onChange={onChange} />)
    const rows = document.querySelectorAll('.spreadsheet-editor-table tbody tr')
    const firstPadRow = rows[2]
    const textboxes = within(firstPadRow).getAllByRole('textbox')
    const exerciseInput = textboxes[1]
    const setsInput = textboxes[2]

    fireEvent.change(exerciseInput, { target: { value: 'Muscle Snatch' } })
    fireEvent.keyDown(exerciseInput, { key: 'Tab' })
    expect(onChange).not.toHaveBeenCalled()

    fireEvent.change(setsInput, { target: { value: '4' } })
    fireEvent.keyDown(setsInput, { key: 'Tab' })
    expect(onChange).not.toHaveBeenCalled()
    fireEvent.keyDown(setsInput, { key: 'Enter' })

    const nextProgram = onChange.mock.calls.at(-1)[0]
    const monday = nextProgram.days.find((d) => d.day === 'Monday')
    const hit = monday.exercises.find((x) => x.name === 'Muscle Snatch')
    expect(hit?.sets).toBe('4')
  })

  it('respects intensityMode=percent_1rm: shows % 1RM, hides RPE and Weight', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} intensityMode="percent_1rm" />)
    const headers = Array.from(document.querySelectorAll('.spreadsheet-editor-table th'))
      .map((el) => el.textContent)
    expect(headers).toContain('% 1RM')
    expect(headers).not.toContain('RPE')
    expect(headers).not.toContain('Weight')
  })

  it('respects intensityMode=rpe: shows RPE only', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} intensityMode="rpe" />)
    const headers = Array.from(document.querySelectorAll('.spreadsheet-editor-table th'))
      .map((el) => el.textContent)
    expect(headers).toContain('RPE')
    expect(headers).not.toContain('% 1RM')
    expect(headers).not.toContain('Weight')
  })

  it('respects intensityMode=weight: shows Weight only', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} intensityMode="weight" />)
    const headers = Array.from(document.querySelectorAll('.spreadsheet-editor-table th'))
      .map((el) => el.textContent)
    expect(headers).toContain('Weight')
    expect(headers).not.toContain('% 1RM')
    expect(headers).not.toContain('RPE')
  })

  it('shows default Sunday tab with entry capacity', () => {
    render(<SpreadsheetEditor programData={programFixture} onChange={() => {}} />)
    fireEvent.click(screen.getByRole('tab', { name: /Sunday/i }))
    const rows = document.querySelectorAll('.spreadsheet-editor-table tbody tr')
    expect(rows.length).toBe(20) // default 4-week block => 5 rows/week template floor
  })

  it('keeps weekday rows sorted by week number after Enter commit', () => {
    const onChange = vi.fn()
    render(<SpreadsheetEditor programData={programFixture} onChange={onChange} />)
    const rows = document.querySelectorAll('.spreadsheet-editor-table tbody tr')
    const rowInWeek4 = rows[15] // week 4 first template row
    const weekInput = within(rowInWeek4).getAllByRole('textbox')[0]
    const exerciseInput = within(rowInWeek4).getAllByRole('textbox')[1]
    fireEvent.change(weekInput, { target: { value: '4' } })
    fireEvent.change(exerciseInput, { target: { value: 'Week4 Lift' } })
    fireEvent.keyDown(exerciseInput, { key: 'Enter' })

    const nextProgram = onChange.mock.calls.at(-1)[0]
    const monday = nextProgram.days.find((d) => d.day === 'Monday')
    const weeks = monday.exercises.map((x) => Number.parseInt(x.week || '999', 10))
    expect(weeks).toEqual([...weeks].sort((a, b) => a - b))
  })

  it('shows first-row hint on first empty row when row one has exercise', () => {
    const program = {
      week_start_date: '2026-04-21',
      days: [
        { day: 'Monday', exercises: [{ name: 'Loaded Row', sets: '5', reps: '2', week: '1' }] },
      ],
    }
    render(<SpreadsheetEditor programData={program} onChange={() => {}} />)
    expect(screen.queryByPlaceholderText('Enter exercise')).toBeTruthy()
  })
})
