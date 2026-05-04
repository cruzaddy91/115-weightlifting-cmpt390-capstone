import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import * as XLSX from 'xlsx'

import {
  INSTRUCTIONS_SHEET,
  PROGRAM_TEMPLATE_COLUMNS,
  PROGRAM_TEMPLATE_SHEET,
  buildTemplateWorkbook,
  expandMultiBlockTemplateRows,
  parseProgramFile,
  pickProgramSheetNameForImport,
} from '../utils/programTemplate'

const makeFileFromAoA = (aoa, sheetName = PROGRAM_TEMPLATE_SHEET) => {
  const worksheet = XLSX.utils.aoa_to_sheet(aoa)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
  const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' })
  return new File([buffer], 'program.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}

const HEADER_ROW = ['Week', 'Day', 'Exercise', 'Sets', 'Reps', '% 1RM', 'RPE', 'Weight', 'Tempo', 'Rest', 'Notes']

describe('programTemplate', () => {
  it('exposes 11 canonical columns in the expanded schema', () => {
    expect(PROGRAM_TEMPLATE_COLUMNS).toEqual([
      'week', 'day', 'exercise', 'sets', 'reps',
      'percent_1rm', 'rpe', 'weight', 'tempo', 'rest', 'notes',
    ])
  })

  it('builds a template workbook with Instructions + Program sheets and frozen header', () => {
    const workbook = buildTemplateWorkbook()
    expect(workbook.SheetNames).toContain(INSTRUCTIONS_SHEET)
    expect(workbook.SheetNames).toContain(PROGRAM_TEMPLATE_SHEET)

    const programSheet = workbook.Sheets[PROGRAM_TEMPLATE_SHEET]
    // Frozen header: the !views descriptor drives the Excel freeze-pane UI.
    expect(programSheet['!views']).toBeTruthy()
    expect(programSheet['!views'][0]).toMatchObject({ state: 'frozen', ySplit: 1 })
    // Header row labels match the schema order.
    const firstRowLabels = HEADER_ROW.map((_, c) => programSheet[XLSX.utils.encode_cell({ r: 0, c })]?.v)
    expect(firstRowLabels).toEqual(HEADER_ROW)
  })

  it('parses a round-trip workbook back to program_data shape with all fields', async () => {
    const rows = [
      HEADER_ROW,
      [1, 'Monday', 'Snatch', 5, 2, '75%', '', '', '', '2min', 'Fast'],
      [1, 'Monday', 'Back Squat', 4, 5, '80%', '', '', '3-1-X-1', '3min', ''],
      [1, 'Tuesday', 'Clean & Jerk', 5, '1+1', '78%', '', '', '', '2-3min', ''],
    ]
    const file = makeFileFromAoA(rows)
    const result = await parseProgramFile(file)

    expect(result.days.map((d) => d.day)).toEqual(['Monday', 'Tuesday'])
    expect(result.days[0].exercises).toHaveLength(2)
    expect(result.days[0].exercises[0]).toMatchObject({
      name: 'Snatch', sets: '5', reps: '2', percent_1rm: '75%', rest: '2min',
      intensity: '75%', week: '1',
    })
    expect(result.days[0].exercises[1].tempo).toBe('3-1-X-1')
    expect(result.days[1].exercises[0].name).toBe('Clean & Jerk')
  })

  it('derives intensity from RPE or Weight when percent_1rm is blank', async () => {
    const rows = [
      HEADER_ROW,
      [1, 'Monday', 'Power Snatch', 5, 2, '', 7, '', '', '90s', 'Speed'],
      [1, 'Tuesday', 'Deadlift', 3, 5, '', '', '180kg', '', '3min', ''],
    ]
    const file = makeFileFromAoA(rows)
    const result = await parseProgramFile(file)
    expect(result.days[0].exercises[0].intensity).toBe('7')
    expect(result.days[0].exercises[0].rpe).toBe('7')
    expect(result.days[1].exercises[0].intensity).toBe('180kg')
    expect(result.days[1].exercises[0].weight).toBe('180kg')
  })

  it('handles case-insensitive headers and alternate percent column names', async () => {
    const rows = [
      ['week', 'Day', 'EXERCISE', 'sets', 'reps', '% 1RM', 'rpe', 'weight', 'tempo', 'rest', 'Notes'],
      ['', 'Wednesday', 'Deadlift', 3, 5, '70%', '', '', '', '', ''],
      ['', '', '', '', '', '', '', '', '', '', ''],
      ['', 'Thursday', '', '', '', '', '', '', '', '', ''],
    ]
    const file = makeFileFromAoA(rows)
    const result = await parseProgramFile(file)
    expect(result.days).toHaveLength(1)
    expect(result.days[0].day).toBe('Wednesday')
    expect(result.days[0].exercises[0].percent_1rm).toBe('70%')
  })

  it('ignores the Instructions sheet on upload', async () => {
    const workbook = XLSX.utils.book_new()
    const instructions = XLSX.utils.aoa_to_sheet([['Do not parse me'], ['Still ignored']])
    const program = XLSX.utils.aoa_to_sheet([
      HEADER_ROW,
      [1, 'Friday', 'Push Press', 4, 5, '70%', '', '', '', '', ''],
    ])
    XLSX.utils.book_append_sheet(workbook, instructions, INSTRUCTIONS_SHEET)
    XLSX.utils.book_append_sheet(workbook, program, PROGRAM_TEMPLATE_SHEET)
    const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' })
    const file = new File([buffer], 'prog.xlsx')

    const result = await parseProgramFile(file)
    expect(result.days[0].day).toBe('Friday')
    expect(result.days[0].exercises[0].name).toBe('Push Press')
  })

  it('throws a readable error on an empty workbook', async () => {
    const workbook = XLSX.utils.book_new()
    const empty = XLSX.utils.aoa_to_sheet([])
    XLSX.utils.book_append_sheet(workbook, empty, PROGRAM_TEMPLATE_SHEET)
    const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' })
    const file = new File([buffer], 'empty.xlsx')
    await expect(parseProgramFile(file)).rejects.toThrow(/empty/i)
  })

  it('expands side-by-side program blocks from one SheetJS row', () => {
    const raw = [
      {
        Week: 1,
        Day: 'Monday',
        Exercise: 'Snatch',
        Sets: '1',
        Reps: '1',
        '% 1RM': '70%',
        RPE: '',
        Weight: '',
        Tempo: '',
        Rest: '',
        Notes: '',
        Week_1: 2,
        Day_1: 'Tuesday',
        Exercise_1: 'Clean & Jerk',
        Sets_1: '2',
        Reps_1: '2',
        '% 1RM_1': '80%',
        RPE_1: '',
        Weight_1: '',
        Tempo_1: '',
        Rest_1: '',
        Notes_1: '',
      },
    ]
    const expanded = expandMultiBlockTemplateRows(raw)
    expect(expanded).toHaveLength(2)
    expect(expanded[0].Exercise).toBe('Snatch')
    expect(expanded[1].Exercise).toBe('Clean & Jerk')
  })

  it('rejects unknown explicit sheet name', async () => {
    const workbook = XLSX.utils.book_new()
    const ws = XLSX.utils.aoa_to_sheet([[HEADER_ROW], [1, 'Mon', 'X', 1, 1, '', '', '', '', '', '']])
    XLSX.utils.book_append_sheet(workbook, ws, '4 Week')
    const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' })
    const file = new File([buffer], 'p.xlsx')
    await expect(parseProgramFile(file, { sheetName: 'No Such Sheet' })).rejects.toThrow(/no sheet named/i)
  })

  it('imports the committed ExcelTables workbook (4 Week tab)', async () => {
    const dir = path.dirname(fileURLToPath(import.meta.url))
    const asset = path.join(dir, '../../public/115wl_program_template_ExcelTables.xlsx')
    const buf = readFileSync(asset)
    const file = new File([buf], '115wl_program_template_ExcelTables.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const wb = XLSX.read(buf, { type: 'array' })
    expect(pickProgramSheetNameForImport(wb)).toBe('4 Week')
    const result = await parseProgramFile(file, { sheetName: '4 Week' })
    expect(result.days.length).toBeGreaterThan(0)
    const exCount = result.days.reduce((t, d) => t + d.exercises.length, 0)
    expect(exCount).toBeGreaterThan(0)
  })
})
