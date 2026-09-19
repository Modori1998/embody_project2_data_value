# Project2 Data Value

Local project repository for Project2 data-value research and implementation.

## Layout

| Path | Role |
| --- | --- |
| `0-doc/` | Authoritative design docs, roadmap, design review, audit and implementation records |
| `configs/` | Phase / contract configuration templates |
| `src/project2_g1/` | G1 signal, boundary, calibration, scoring and reporting library |
| `src/project2_g1_audit_web/` | Human-audit web application (Flask app + templates) |
| `scripts/` | Entry-point runners for each G1 phase |
| `tests/` | Pytest suites and fixtures |
| `outputs/` | Generated run artifacts (plots, videos, tables, local review DBs) — **not tracked** |

`outputs/` is intentionally excluded from version control; it is regenerable
run output, not source. See `.gitignore`.
