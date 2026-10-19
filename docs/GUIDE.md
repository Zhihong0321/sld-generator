# User guide

How to use this repository to produce Solar ATAP SLDs, either by yourself or through an
AI agent. For command details see [TOOLS.md](TOOLS.md); for the agent rules see
[../AGENTS.md](../AGENTS.md).

## Contents
1. [Install](#1-install)
2. [Your first drawing in 5 minutes](#2-your-first-drawing-in-5-minutes)
3. [Working with an AI agent](#3-working-with-an-ai-agent)
4. [The project file](#4-the-project-file)
5. [Adding equipment to the library](#5-adding-equipment-to-the-library)
6. [Reading check results](#6-reading-check-results)
7. [Revisions](#7-revisions)
8. [Changing the engineering rules](#8-changing-the-engineering-rules)
9. [Sharing with your team](#9-sharing-with-your-team)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Install
You need Python 3.10 or newer and Microsoft Edge (built into Windows 10/11) or Google Chrome.

**One line** (also updates an existing install, keeping your `projects/` and `library/`):
```powershell
irm https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.ps1 | iex   # Windows
```
```bash
curl -fsSL https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.sh | bash   # macOS / Linux
```
This installs to `~/sld-generator`; set `SLD_HOME` first to choose another folder.

**Manual:**
```bash
git clone https://github.com/Zhihong0321/sld-generator.git
cd sld-generator
pip install -e .
sldgen doctor
```
`doctor` should end with **All good.** No other packages are needed.

## 2. Your first drawing in 5 minutes
1. **See what equipment is available:**
   ```bash
   sldgen library
   ```
2. **Create the job file.** This example is 17 panels as strings of 9 and 8 on the two MPPTs:
   ```bash
   sldgen init projects/ATAP-SLD-RES-010.json --phase 3 --module jinko-jkm650n-66ql6-bdv --inverter saj-r6-10k-t2 --strings 9,8
   ```
3. **Fill in the customer details:** open `projects/ATAP-SLD-RES-010.json` and complete `project`
   (account holder, address, TNB account no.), `cables` (run lengths) and `people`
   (QP/CP). Anything left blank prints as a blank on the sheet.
4. **Check the design:**
   ```bash
   sldgen check projects/ATAP-SLD-RES-010.json
   ```
5. **Build the drawing:**
   ```bash
   sldgen build projects/ATAP-SLD-RES-010.json
   ```
   Open `output/ATAP-SLD-RES-010/ATAP-SLD-RES-010_Rev01.pdf`.

The two files in `examples/` are complete reference jobs. Copy one if that's easier.

## 3. Working with an AI agent
The agent does steps 1-5 for you. It reads [AGENTS.md](../AGENTS.md), which tells it to:
- collect the job using [templates/intake-checklist.md](../templates/intake-checklist.md), asking you once for anything missing
- look up or add the equipment (reading the manufacturer datasheets)
- write the project file, run `check`, explain any errors and propose fixes
- build the PDF, review the preview, and report back with a summary, warnings and missing fields

| Agent | What to do |
|---|---|
| Claude Code | Open the folder; ask *"generate an SLD for …"* (the skill loads automatically) |
| Codex CLI, Cursor, Copilot agent, Gemini CLI, Aider, Windsurf | Open the folder; ask *"Follow AGENTS.md: generate an SLD for …"* |
| Any other agent with a terminal | *"Read AGENTS.md in this repo and follow it to generate an SLD for …"* |

**Tips for good results**
- Attach datasheet PDFs for any panel or inverter that's new to the library. The agent can
  then mark the entry *verified* and the PRELIMINARY warning disappears.
- Give exact model codes ("SAJ R6-10K-T2", not "SAJ 10k").
- A photo of the TNB bill gets the name and account number exactly right.
- The agent will tell you which defaults it used (cable lengths, MDB ratings). Correct
  them and ask for a new revision.

## 4. The project file
One JSON file per job, in `projects/`. The full field list with descriptions is in
[schema/project.schema.json](../schema/project.schema.json). The essentials:

```json
{
  "project": { "account_holder": "...", "address": "...", "tnb_account_no": "...",
               "drawing_no": "ATAP-SLD-RES-010", "revision": "01", "date": "2026-10-19" },
  "supply":   { "phase": 3 },
  "pv_module": "jinko-jkm650n-66ql6-bdv",
  "inverter":  "saj-r6-10k-t2",
  "array":    { "strings": [ { "mppt": 1, "modules": 9 }, { "mppt": 2, "modules": 8 } ] },
  "cables":   { "dc_length_m": 20, "ac_length_m": 15 }
}
```

- **Strings:** each entry is one string (`modules` in series) on an MPPT. `"count": 2` adds
  identical parallel strings on the same MPPT. Parallel strings must be the same length.
- **Equipment:** a library key (recommended), or a full inline object for a one-off.
- **What you never enter:** breaker, RCD, isolator, SPD, fuse and cable sizes. The engine
  sizes them. To force one, see [section 8](#8-changing-the-engineering-rules).

## 5. Adding equipment to the library
1. Get the manufacturer datasheet PDF.
2. Copy the object from [templates/module.json](../templates/module.json) or
   [templates/inverter.json](../templates/inverter.json) into `library/modules.json` or
   `library/inverters.json` under a new lower-case key (e.g. `longi-lr7-54hvh-485m`).
3. Fill in the values from the datasheet:
   - Modules: use the STC table column for the exact wattage. Temperature coefficients are
     negative %/°C. The max series fuse rating is on the "application conditions" table.
   - Inverters: add one entry per size in a series. `max_ac_current_a` is the maximum output
     current, and `max_isc_per_mppt_a` is the DC short-circuit current limit.
4. Set `"verified": true` and note the datasheet name and edition in `remarks`.
5. Run `sldgen library` to confirm it appears.

## 6. Reading check results
- **PASSED:** buildable. Read any warnings anyway.
- **FAILED:** at least one rule is broken. Typical fixes:

| Error | Usual fix |
|---|---|
| `dc.voc_max` (Voc too high when cold) | Fewer modules per string |
| `dc.isc` (MPPT current too high) | Fewer parallel strings on that MPPT, or an inverter with a higher MPPT current |
| `mppt.inputs` | The inverter takes only N strings per MPPT, so move strings to another MPPT |
| `dc.vd` / `ac.vd` | Shorter run, or let the engine pick a bigger cable (remove any forced size) |
| `cap.ac` | Smaller inverter (ATAP cap is 5 kW single-phase / 15 kW three-phase) |

- **Warnings worth acting on:** `dc.vmp_min` (string too short for hot days), `ratio.high`
  (heavy clipping), `data.unverified` (drawing will say PRELIMINARY).

The design report (`*_design-report.md`) beside the PDF lists every check and the full
equipment schedule. It's useful for the QP's review.

## 7. Revisions
Edit the project file, increment `"revision"` (`"01"` → `"02"`), and build again. Each
revision gets its own file name in the same output folder, so earlier revisions are kept.

## 8. Changing the engineering rules
| Scope | Where | Example |
|---|---|---|
| One job | `overrides` in the project file | `"overrides": {"ac_mcb_a": 32, "ac_rcd_ma": 30}` |
| One job | `cables.dc_size_mm2` / `cables.ac_size_mm2` | Force 6 mm² AC cable |
| One job | `site` | `"t_min_cell_c": 5` for a highland site |
| All jobs | `sldgen/rules.py` | Voltage drop limits, standard breaker sizes, RCD sensitivity, ATAP caps, protection settings table |

Overrides below the calculated minimum are rejected with an error. After editing
`rules.py`, run `sldgen doctor` to confirm the examples still pass.

## 9. Sharing with your team
- **One-line install (recommended):** send colleagues the installer line from
  [section 1](#1-install). Re-running it updates them to the latest version.
- **Contributing back:** library additions and rule changes go into the GitHub repo as
  normal commits (or pull requests). `output/` is git-ignored.
- **Shared library:** point everyone's `SLD_LIBRARY` environment variable at one folder
  (e.g. a network drive) so equipment is added once for the whole team.

## 10. Troubleshooting
| Symptom | Fix |
|---|---|
| `sldgen: command not found` | Run `pip install -e .` in the repo, or use `python -m sldgen …` |
| `PDF export failed` / doctor shows no browser | Install Edge or Chrome, or set `SLD_BROWSER` to its .exe path |
| `PROJECT FILE INCOMPLETE` | The listed fields are missing. The message names each one. |
| Key `… not found in library` | Run `sldgen library` for valid keys, or add the equipment (section 5) |
| Text looks wrong on the sheet | Report it, or fix `sldgen/render.py` and rebuild. Never edit the PDF/SVG. |
