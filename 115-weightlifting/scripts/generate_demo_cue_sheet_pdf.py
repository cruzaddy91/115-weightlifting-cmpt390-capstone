#!/usr/bin/env python3
"""One-off generator: demo screen-record cue sheet PDF (plain text, prints cleanly)."""

from pathlib import Path

from fpdf import FPDF


class CuePDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def main():
    out = Path.home() / "Desktop" / "Demo_Screen_Record_Cue_Sheet.pdf"
    pdf = CuePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(left=18, top=18, right=18)
    pdf.add_page()
    col_w = pdf.w - pdf.l_margin - pdf.r_margin

    def h1(text: str):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(col_w, 9, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def h2(text: str):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(col_w, 7, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def body(text: str):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", size=11)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(col_w, 5.5, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def bullets(lines: list[str]):
        pdf.set_font("Helvetica", size=11)
        pdf.set_text_color(30, 30, 30)
        for line in lines:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(col_w, 5.5, f"- {line}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    h1("115 Weightlifting - Demo cue sheet")
    body(
        "Screen-record flow (top to bottom): Head Coach, then Coach, then Athlete. "
        "Use this as a teleprompter-style checklist on iPad; check boxes mentally as you go."
    )

    h2("Before you record")
    bullets(
        [
            "Quiet tab noise; close unrelated windows.",
            "Know three logins: head coach, line coach, athlete (or use three browsers/profiles).",
            "Have the filled workbook ready: Desktop / TEST1_8_week_upload_template.xlsx (use the 8 Week sheet when importing).",
            "Decide if you want voiceover: then allow mic when macOS asks (Shift-Command-5).",
        ]
    )

    h2("1) Head coach - control, management, useful functions")
    bullets(
        [
            "Open Organization overview: per-coach rollups (athletes, programs, PRs, workout logs).",
            "Show line coach governance: invite/link a coach by username (Add to org); show staff list.",
            "Athlete accountability: roster table - assign each athlete's primary (accountable) coach.",
            "Executive analytics: recommendation engine strip (mode, version, fallback if any).",
            "De-identified analytics blocks: style outcomes, normalized program names, segment recommendations.",
            "Optional: mention head can open Coach workspace from the link when you need the same tools as a line coach.",
        ]
    )

    h2("2) Coach - governance of athletes; card + spreadsheet + upload")
    bullets(
        [
            "Switch to Coach workspace; orient: roster or athlete list, programs for the selected athlete.",
            "Governance narrative: you see and manage all athletes assigned to you; programs and edits are scoped to permissions.",
            "Card mode: show program as cards / structured blocks athletes recognize.",
            "Spreadsheet mode: toggle into grid editing; quick edits across days/weeks.",
            "Excel upload: import from the filled template - choose Import worksheet (e.g. 8 Week), confirm parse, fix any row warnings if shown.",
            "Show publish/save flow: program name, dates, assign to athlete - tie back to what the head coach sees in rollups.",
        ]
    )

    h2("3) Athlete - general experience")
    bullets(
        [
            "Athlete home: today, selected day, completion counts, streak/lifetime if populated.",
            "Quick glance strip: programs assigned, active block end, planned exercise volume, last coach update.",
            "Logging flow: mark sets complete; save feedback; optional drawer (workout / PR / stats).",
            "Close loop: mention coach/head sees aggregates - not surveillance of one tap, but org health.",
        ]
    )

    h2("Closing line (optional)")
    body(
        "One sentence: single product with three lenses - executive oversight, coaching operations, athlete execution."
    )

    pdf.add_page()
    h1("Screen recording on Mac - quick answers")
    body("Yes. macOS includes screen recording without extra apps.")
    h2("Fast path (recommended)")
    bullets(
        [
            "Press Shift-Command-5. Choose Record Entire Screen or Record Selected Portion.",
            "Click Options: pick microphone if narrating; choose where to save (Desktop or Movies).",
            "Click Record; use the menu bar stop button or Shift-Command-5 again to stop.",
        ]
    )
    h2("QuickTime path")
    bullets(
        [
            "QuickTime Player > File > New Screen Recording (older workflow; still works on many setups).",
        ]
    )
    h2("Tips")
    bullets(
        [
            "Do a 10-second dry run to confirm resolution and that the correct display is captured.",
            "If demoing Safari logins, use Private windows or separate browser profiles to avoid cross-logout.",
        ]
    )

    pdf.output(str(out))
    print(out)


if __name__ == "__main__":
    main()
