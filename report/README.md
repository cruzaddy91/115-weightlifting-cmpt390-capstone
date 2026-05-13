# CMPT 390 capstone PDF report

Source: [CMPT390_115_Report.qmd](CMPT390_115_Report.qmd) (Quarto, same layout pattern as the DATA 470 capstone report: Westminster title page, two-column `scrartcl`, custom header, logo strip before references).

## Render

**macOS** with Quarto and MacTeX installed:

```bash
cd report
quarto render CMPT390_115_Report.qmd --to pdf
```

**Headless (Docker, no local Quarto/TeX):** from the repository root:

```bash
./report/render_pdf_docker.sh
```

The DATA 470 report pins Word fonts (Times New Roman, etc.). This project’s `_quarto.yml` omits those lines so the same Docker recipe compiles on Linux images; if you want an exact font match on macOS, add `mainfont`, `sansfont`, and `monofont` under `format.pdf` like [DATA-470 `_quarto.yml`](../../data-470-dscapstone/report/_quarto.yml) and render locally.

Output PDF: `output/CMPT390_115_Report.pdf`.
