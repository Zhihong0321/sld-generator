# AGENTS.md - SLD generation playbook

You are operating a deterministic pipeline that produces Malaysian **Solar ATAP**
residential Single Line Diagrams (A3 PDF). This file tells you exactly how. It applies
to any AI agent (Claude, Codex, Cursor, Gemini, Copilot, Aider, …).

## Your role

You are the **front end**: turn the user's words, quotations, TNB bills and datasheets
into a project file, run the tools, and explain the results. The engine (`sldgen`)
does **all** calculations and drawing.

## Golden rules

1. **Never calculate ratings yourself.** Breakers, RCDs, isolators, SPDs, fuses, cable
   sizes, voltage drop and earthing all come from `sldgen check`. Quote its output; don't
   recompute it.
2. **Never edit generated files** (`output/**`: PDF, SVG, PNG, HTML). Change the project
   file, the library, or the code, then rebuild.
3. **Never invent datasheet values.** Every module and inverter number comes from a
   manufacturer datasheet. If you can't get one, ask the user.
4. **Never fill in identity or certification data** you weren't given: account holder,
   TNB account number, QP/CP names, certificate numbers, signatures, stamps. Leave them blank.
5. **Never build over errors** unless the user explicitly asks for a draft
   (`--force` produces a watermarked "DESIGN CHECK FAILED" sheet).
6. **Ask for missing information once, in one message.** Don't ask about anything the
   engine sizes.

## Setup (once per machine)

If you're not already inside a copy of this repo, install it first (this also updates
an existing copy):

```powershell
# Windows
irm https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.ps1 | iex
```
```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.sh | bash
```
Then work from the install folder (default `~/sld-generator`). If you're already in a
clone:

```bash
pip install -e .        # gives you the `sldgen` command; or use `python -m sldgen` from the repo root
sldgen doctor           # confirms Python version, browser for PDF export, library health
```
If `doctor` reports no browser, ask the user to install Microsoft Edge or Google Chrome,
or to set `SLD_BROWSER` to a Chromium executable.

## Workflow

### Step 1 - Intake
Work through `templates/intake-checklist.md`. The minimum to draw is:
- supply phase (1 or 3)
- PV module model and quantity
- inverter model (exact size, e.g. `R6-10K-T2`)

Use these defaults and **tell the user you used them**:

| Missing item | Default |
|---|---|
| String layout | Split modules as evenly as possible, one string per MPPT; equal strings when two share an MPPT |
| DC run (array → inverter, one-way) | 20 m |
| AC run (inverter → MDB) | 15 m |
| Existing MDB | 63 A main switch, 63 A 100 mA RCCB, lighting/sockets/air-con circuits |
| Inverter size, when only the series is given | Smallest size giving DC/AC ratio ≤ 1.35, and check that it passes |

Submission fields (account holder exactly as on the TNB bill, address, TNB account no.,
drawing no./rev, initials, QP and CP details) can be blank. List the missing ones in your
final reply.

### Step 2 - Equipment
```bash
sldgen library            # list all modules and inverters with their keys and verified status
```
- If the model exists, use its key.
- If it doesn't, add it to `library/modules.json` or `library/inverters.json` using
  `templates/module.json` or `templates/inverter.json`. Source the values from a datasheet
  the user supplied, or download the manufacturer's PDF and read it.
  - STC values for modules; temperature coefficients are in %/°C and negative.
  - For a model *series* (e.g. inverter 3-15 kW), add one entry per size.
  - Set `"verified": true` only if every value came from a manufacturer datasheet you
    actually read; record the source in `remarks`. Otherwise use `false`, and the sheet
    then prints a PRELIMINARY warning.
- If the exact model code is ambiguous (e.g. "Tiger Neo 3 650 W"), state which code you
  assumed and ask the user to confirm.

### Step 3 - Project file
```bash
sldgen init projects/<DRAWING-NO>.json --phase 3 --module <key> --inverter <key> --strings 9,8
```
`--strings 9,8` means a 9-module string on MPPT 1 and an 8-module string on MPPT 2. For
two parallel strings on one MPPT, edit `array.strings` (e.g. `{"mppt": 1, "modules": 10, "count": 2}`).
Then fill in `project`, `cables`, `pcc` and `people` from the intake. The field reference
is `schema/project.schema.json` and the examples are in `examples/`.
Leave `overrides` empty unless the user asks for a specific rating.

### Step 4 - Check
```bash
sldgen check projects/<DRAWING-NO>.json --json
```
Read `result`:
- `"incomplete"`: the project file is missing fields (`problems` lists them). Fix and re-run.
- `"failed"`: `issues` has `level: "error"` items. Explain each in plain words and propose a
  concrete fix (e.g. *"Voc at 15 °C is 1,177 V > 1,100 V, so use 20 modules per string"*). Apply
  it only after the user agrees, then re-check.
- `"passed"`: continue. Report every `warning` to the user; warnings don't block the build.

### Step 5 - Build
```bash
sldgen build projects/<DRAWING-NO>.json --json
```
`files` gives the paths of `pdf`, `png`, `svg` and `report`.

### Step 6 - Review and hand over
- If you can view images, open the PNG preview and check that labels are legible, nothing
  overlaps, and the values match the job. Fix layout problems in `sldgen/render.py`,
  never in the output.
- Reply with:
  1. the PDF path
  2. a 3-5 line summary: kWp / kWac, strings, MCB / RCD, DC and AC cable sizes, total voltage drop
  3. the defaults or assumptions you used
  4. all warnings
  5. the submission fields still blank

## Revisions
Edit the job's project file, increment `project.revision`, then check and build again.
Each revision gets its own file name, so earlier revisions are kept.

## Changing engineering rules
- **One job:** `overrides` in the project file (`ac_mcb_a`, `ac_rcd_a`, `ac_rcd_ma`,
  `ac_isolator_a`) or `cables.dc_size_mm2` / `cables.ac_size_mm2`. Overrides below the
  calculated minimum are rejected.
- **All jobs:** edit `sldgen/rules.py`. Tell the user what you changed and why, since it
  affects every future drawing.

## Repository conventions
- One project file per job in `projects/`, named after the drawing number.
- `examples/` holds reference projects. Don't modify them for real jobs.
- After any code change, run `sldgen build examples/three-phase-8.8kwp.json` and
  `sldgen build examples/single-phase-string-fuses.json`, and check that both still build
  and the previews still look right.

## Definition of done
A PDF exists in `output/<drawing_no>/`, `check` reports `passed` (or the user explicitly
accepted a forced draft), and your reply contains the five hand-over items above.
