#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm --entrypoint "" \
  -v "${ROOT}:/work" \
  -w /work/report \
  pandoc/ubuntu-latex:latest \
  bash -c 'set -euo pipefail
    apt-get update -qq && apt-get install -y -qq curl ca-certificates
    curl -fsSL -o /tmp/quarto.deb "https://github.com/quarto-dev/quarto-cli/releases/download/v1.9.37/quarto-1.9.37-linux-amd64.deb"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /tmp/quarto.deb || apt-get -fy install -qq
    quarto render CMPT390_115_Report.qmd --to pdf'
echo "Wrote ${ROOT}/report/output/CMPT390_115_Report.pdf"
