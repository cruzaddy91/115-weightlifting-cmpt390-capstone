#!/usr/bin/env node
/**
 * Writes a small demo workbook to the user's Desktop illustrating Excel vs web-app gaps.
 * Run from repo: node tools/write_web_excel_limitations_demo.cjs
 */
const path = require('path')
const fs = require('fs')
const XLSX = require(path.join(__dirname, '../src/frontend/node_modules/xlsx'))

const desktop = process.env.HOME
  ? path.join(process.env.HOME, 'Desktop')
  : path.join(__dirname, '..')

if (!fs.existsSync(desktop)) {
  console.error('Desktop folder not found:', desktop)
  process.exit(1)
}

const readMe = [
  ['115 Weightlifting — Web vs Excel limitations (demo)'],
  [''],
  ['This file is NOT the official coach template. It is a teaching artifact.'],
  [''],
  ['What Excel can express that the in-app spreadsheet does not mirror 1:1:'],
  [''],
  ['1) Separate sheets (4 Week / 8 Week / 16 Week). The web editor is one flat grid;'],
  ['   import reads one tab at a time (see Import tab in the app).'],
  [''],
  ['2) Extra columns (e.g. "PrivateNote" on the sample "4 Week" sheet).'],
  ['   The app importer only keeps the canonical program columns.'],
  [''],
  ['3) Workbook chrome: native Tables, filters, freeze panes, themes, data validation.'],
  ['   The web grid only echoes header colors from the official template styling.'],
  [''],
  ['4) Side-by-side blocks with _1 / _2 column suffixes (8 / 16 Week official tabs).'],
  ['   The importer flattens these into one program; the web UI does not show blocks side by side.'],
  [''],
  ['5) Formulas: Excel recalculates; import reads stored/displayed cell values via SheetJS.'],
  [''],
]

const headers = [
  'Week',
  'Day',
  'Exercise',
  'Sets',
  'Reps',
  '% 1RM',
  'RPE',
  'Weight',
  'Tempo',
  'Rest',
  'Notes',
  'PrivateNote',
]
const rows = [
  [1, 'Monday', 'Snatch', 5, 2, '75%', '', '', '', '2min', 'Visible in app', 'Dropped on import — not in schema'],
  [1, 'Monday', 'Back Squat', 4, 5, '80%', '', '', '3-1-X-1', '3min', '', ''],
]

const wb = XLSX.utils.book_new()
const ws0 = XLSX.utils.aoa_to_sheet(readMe)
XLSX.utils.book_append_sheet(wb, ws0, 'Read me')

const ws4 = XLSX.utils.aoa_to_sheet([headers, ...rows])
XLSX.utils.book_append_sheet(wb, ws4, '4 Week')

const outPath = path.join(desktop, '115wl_web_vs_excel_limitations.xlsx')
XLSX.writeFile(wb, outPath)
console.log('Wrote', outPath)
