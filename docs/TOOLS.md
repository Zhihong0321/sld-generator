# Tools reference - `sldgen`

Install once from the repo root with `pip install -e .`. Or run any command as
`python -m sldgen …` from the repo root, with no install.

Every command except `schema` accepts `--json` for machine-readable output. That's the
mode AI agents should use.

| Command | Purpose |
|---|---|
| [`sldgen doctor`](#doctor) | Check that this machine can run the pipeline |
| [`sldgen library`](#library) | List the modules and inverters available |
| [`sldgen init`](#init) | Create a project file from the template |
| [`sldgen check`](#check) | Run calculations and compliance checks (no files written) |
| [`sldgen build`](#build) | Check, then write the PDF, PNG, SVG and design report |
| [`sldgen schema`](#schema) | Print the project file JSON Schema |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK / design passed |
| 1 | Design check failed (errors in `issues`), or a forced draft was built |
| 2 | Project file incomplete or unreadable, or bad arguments |
| 3 | Environment problem: no browser for PDF export, or `doctor` found problems |

---

## doctor
```bash
sldgen doctor [--json]
```
Checks the Python version (≥ 3.10), finds Edge/Chrome for PDF export, counts library
entries (listing unverified ones), and runs `check` on every file in `examples/`.

## library
```bash
sldgen library [pv_module|inverter] [--json]
```
Lists library keys with their headline specs and verified status. `--json` returns the
full entries. The library files are `library/modules.json` and `library/inverters.json`;
set the `SLD_LIBRARY` environment variable to use a library folder elsewhere (e.g. a
shared team drive).

## init
```bash
sldgen init <project.json> [--phase 1|3] [--module KEY] [--inverter KEY]
                           [--strings 9,8] [--drawing-no NO] [--overwrite] [--json]
```
Copies `templates/project.json` to the given path, sets today's date, and sets the
drawing number (default: the file name).
- `--strings 9,8` gives one string per MPPT, in MPPT order (9 modules on MPPT 1, 8 on MPPT 2).
  For parallel strings on one MPPT, edit `array.strings` afterwards, e.g.
  `{"mppt": 1, "modules": 10, "count": 2}`.
- The output lists what is still missing before `check` can run.

## check
```bash
sldgen check <project.json> [--json]
```
Runs every calculation in spec §3 and every rule in `sldgen/rules.py`. It writes no files.

JSON output:
```json
{
  "result": "passed | failed | incomplete",
  "summary": {
    "p_dc_kwp": 11.05, "p_ac_kw": 10.0, "dc_ac_ratio": 1.105,
    "strings": [{"mppt": 1, "series": 9, "parallel": 1, "voc_max_v": 463.2, "isc_a": 15.98}],
    "dc_cable_mm2": 6, "vd_dc_pct": 0.673, "dc_isolator": "4P 1000 V DC 25 A", "dc_spd_ucpv_v": 600,
    "string_fuse_a": null, "i_ac_a": 16.7, "ac_mcb": "25 A TP C 10 kA",
    "ac_rcd": "25 A 4P 100 mA Type A", "ac_isolator": "25 A 4P",
    "ac_cable": "4C 4 mm² PVC/PVC Cu + 1C 6 mm² E", "vd_ac_pct": 0.61, "vd_total_pct": 1.283,
    "unverified_equipment": []
  },
  "issues": [{"level": "error | warning | info", "code": "dc.voc_max", "msg": "…"}]
}
```
`incomplete` has a `problems` list in place of `summary`/`issues`.

### Issue codes
| Code | Level | Meaning |
|---|---|---|
| `inverter.phase` | error | Inverter phase ≠ supply phase |
| `mppt.index` / `mppt.mismatch` / `mppt.inputs` | error | Bad MPPT number, unequal parallel strings, too many strings per MPPT |
| `dc.voc_max` | error | Cold-temperature string Voc ≥ inverter max DC voltage |
| `dc.isc` | error | MPPT short-circuit current > inverter limit |
| `dc.vmp_min` / `dc.vmp_max` | warning | Hot/cold Vmp outside the MPPT window (yield loss) |
| `dc.imp` | warning | Operating current above inverter input limit (clipping) |
| `dc.fuse` | error | Required string fuse > module max series fuse |
| `dc.cable` / `dc.vd` / `dc.iz` | error | No DC cable meets voltage drop / ampacity |
| `dc.isolator` / `dc.spd` | error | No standard rating large enough |
| `ac.cable` / `ac.vd` / `ac.iz` | error | No AC cable meets voltage drop / ampacity |
| `vd.total` | error | DC + AC voltage drop > 2 % |
| `cap.ac` | error | Inverter kWac above the Solar ATAP cap (5 kW 1-ph / 15 kW 3-ph) |
| `cap.dc` | warning | Array kWp above the cap - confirm the quota basis |
| `ratio.high` / `ratio.low` | warning | DC/AC ratio outside 0.80-1.35 |
| `pcc.rating` | error | Solar way larger than the MDB main switch |
| `override.*` | error / info | Override below the minimum (error) or applied (info) |
| `module.temp_coeff` | warning | Temperature coefficient missing, default assumed |
| `data.unverified` | warning | Equipment not verified against a datasheet |
| `mppt.unused` | info | Spare MPPT inputs |

## build
```bash
sldgen build <project.json> [--out DIR] [--force] [--no-png] [--json]
```
Runs `check`. If it passes, writes to `output/<drawing_no>/` (or `--out`):

| File | Content |
|---|---|
| `<drawing_no>_Rev<rev>.pdf` | A3 landscape drawing, the deliverable |
| `<drawing_no>_Rev<rev>_preview.png` | 2× raster preview for visual review |
| `<drawing_no>_Rev<rev>.svg` | Vector source |
| `<drawing_no>_Rev<rev>_design-report.md` | Status, issues, checks, string data, equipment schedule |

`--force` builds even when the check fails. The sheet is watermarked **DESIGN CHECK
FAILED - NOT FOR SUBMISSION** and the exit code is 1. JSON output is the same as `check`
plus `"files": {"pdf": …, "png": …, "svg": …, "report": …}`.

PDF export uses headless Microsoft Edge or Google Chrome, found automatically. Set
`SLD_BROWSER` to the path of a Chromium-based browser to choose one.

## schema
```bash
sldgen schema
```
Prints `schema/project.schema.json`. Point editors or validators at that file to get
autocomplete and validation for project files.
