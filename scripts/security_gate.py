#!/usr/bin/env python3
"""Repo-local security gate for accidental secret and sensitive-data commits.

The scanner is intentionally dependency-free so it can run from git hooks and
GitHub Actions. It allows this repo's documented demo-only credentials while
blocking live-looking secrets, private keys, accidental env files, and non-demo
email addresses.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BLOCKED_PATH_NAMES = {'.env'}
BLOCKED_PATH_SUFFIXES = ('.pem', '.key', '.p12', '.pfx')
ALLOWED_ENV_EXAMPLES = {'.env.example'}

SAFE_VALUES = {
    '',
    'change-this-to-a-long-random-secret-for-real-deployment',
    'docker-uat-coach',
    'longenoughpw1',
    'nope',
    'Passw0rd!123',
    'pw',
    'secret-2026',
    'weightlifting_password',
}
SAFE_VALUE_PREFIXES = (
    'archived_',
    'http://localhost',
    'http://127.0.0.1',
)
SAFE_EMAIL_DOMAINS = {
    'example.invalid',
    'uat.example.invalid',
}
CODE_SUFFIXES = {
    '.html',
    '.js',
    '.jsx',
    '.py',
    '.sh',
    '.ts',
    '.tsx',
}

SECRET_ASSIGNMENT_RE = re.compile(
    r'''(?ix)
    \b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)\b
    \s*[:=]\s*
    (?P<quote>["']?)
    (?P<value>[^"'\s#]+)
    ''',
)
EMAIL_RE = re.compile(r'\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b', re.IGNORECASE)

PATTERNS = (
    ('private key block', re.compile(r'-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----')),
    ('AWS access key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('GitHub token', re.compile(r'\bgh[pousr]_[A-Za-z0-9_]{36,}\b')),
    ('OpenAI token', re.compile(r'\bsk-[A-Za-z0-9_-]{32,}\b')),
    ('Slack token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{20,}\b')),
    ('Stripe live secret', re.compile(r'\bsk_live_[A-Za-z0-9]{20,}\b')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
)


@dataclass
class Finding:
    path: str
    line: int
    kind: str
    detail: str


def git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(
        ['git', *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def candidate_files(mode: str) -> list[Path]:
    if mode == 'staged':
        names = git_lines(['diff', '--cached', '--name-only', '--diff-filter=ACMR'])
    elif mode == 'tracked':
        names = git_lines(['ls-files'])
    else:
        tracked = set(git_lines(['ls-files']))
        untracked = set(git_lines(['ls-files', '--others', '--exclude-standard']))
        names = sorted(tracked | untracked)
    return [ROOT / name for name in names]


def is_safe_secret_value(value: str) -> bool:
    stripped = value.strip().strip('"\'')
    lower = stripped.lower()
    if stripped in SAFE_VALUES:
        return True
    if any(stripped.startswith(prefix) for prefix in SAFE_VALUE_PREFIXES):
        return True
    if lower in {'true', 'false', 'none', 'null'}:
        return True
    if lower.startswith(('example', 'placeholder', 'dummy', 'test_', 'uat_')):
        return True
    if 'example.invalid' in lower:
        return True
    return False


def is_code_expression(path: Path, value: str, quote: str) -> bool:
    if quote or path.suffix not in CODE_SUFFIXES:
        return False
    stripped = value.strip()
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', stripped):
        return True
    return any(marker in stripped for marker in ('(', ')', '[', ']', '{', '}', '.', ','))


def path_findings(path: Path) -> list[Finding]:
    rel = path.relative_to(ROOT).as_posix()
    findings: list[Finding] = []
    if path.name in BLOCKED_PATH_NAMES or (
        path.name.startswith('.env.') and path.name not in ALLOWED_ENV_EXAMPLES
    ):
        findings.append(Finding(rel, 0, 'blocked file', 'environment files must not be committed'))
    if path.suffix in BLOCKED_PATH_SUFFIXES:
        findings.append(Finding(rel, 0, 'blocked file', f'{path.suffix} key/certificate material is not allowed'))
    return findings


def scan_text(path: Path, text: str) -> list[Finding]:
    rel = path.relative_to(ROOT).as_posix()
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(Finding(rel, line_no, name, 'live-looking secret pattern'))

        assignment = SECRET_ASSIGNMENT_RE.search(line)
        if (
            assignment
            and not is_code_expression(path, assignment.group('value'), assignment.group('quote'))
            and not is_safe_secret_value(assignment.group('value'))
        ):
            findings.append(
                Finding(
                    rel,
                    line_no,
                    'credential assignment',
                    f"{assignment.group(1)} has a non-placeholder value",
                ),
            )

        for email_match in EMAIL_RE.finditer(line):
            domain = email_match.group(1).lower()
            if domain not in SAFE_EMAIL_DOMAINS:
                findings.append(Finding(rel, line_no, 'non-demo email address', email_match.group(0)))
    return findings


def scan_file(path: Path) -> list[Finding]:
    findings = path_findings(path)
    if not path.exists() or not path.is_file():
        return findings
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [*findings, Finding(path.relative_to(ROOT).as_posix(), 0, 'read error', str(exc))]
    if b'\0' in raw:
        return findings
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')
    return [*findings, *scan_text(path, text)]


def main() -> int:
    parser = argparse.ArgumentParser(description='Scan repo files for accidental secrets and sensitive data.')
    parser.add_argument(
        '--mode',
        choices=('tracked', 'staged', 'all'),
        default='tracked',
        help='Files to scan. Use staged from git hooks, tracked in CI, all for local paranoia.',
    )
    args = parser.parse_args()

    findings: list[Finding] = []
    for path in candidate_files(args.mode):
        findings.extend(scan_file(path))

    if findings:
        print('Security gate failed. Review these findings before committing/pushing:', file=sys.stderr)
        for finding in findings:
            location = finding.path if finding.line == 0 else f'{finding.path}:{finding.line}'
            print(f'- {location}: {finding.kind}: {finding.detail}', file=sys.stderr)
        return 1

    print(f'Security gate passed ({args.mode} files).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
