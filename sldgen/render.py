"""Render a complete A3-landscape SLD sheet as SVG. All units are millimetres.

Sheet zones:
  diagram      x 10-316, y 10-191   L-shaped flow: PV (top-left) down to the
                                    inverter, then AC left-to-right to the TNB grid
  schedule     x 10-316, y 191-287  equipment schedule with full specifications
  side column  x 316-410            protection settings, design checks, notes,
                                    title block (follows the Eternalgy sheet)
"""

import math
from xml.sax.saxutils import escape

from . import rules as R

W, H = 420, 297
SCHED_W = 155.0         # equipment schedule width; the QP / CP endorsement blocks sit to its right
FONT = "Arial, Helvetica, sans-serif"
CHAR_W = 0.56          # average glyph advance as a fraction of the font size
GREEN = "#1a7f37"
RED = "#c00000"

CSS = f"""
.ln{{stroke:#000;stroke-width:.3;fill:none;stroke-linecap:round;stroke-linejoin:round}}
.th{{stroke:#000;stroke-width:.18;fill:none}}
.hv{{stroke:#000;stroke-width:.55;fill:none}}
.bus{{stroke:#000;stroke-width:1.3;fill:none}}
.en{{stroke:{GREEN};stroke-width:.3;fill:none;stroke-dasharray:1.6 .8}}
.es{{stroke:{GREEN};stroke-width:.3;fill:none}}
.box{{stroke:#000;stroke-width:.25;fill:none;stroke-dasharray:2 1}}
.dm{{stroke:{RED};stroke-width:.7;fill:none;stroke-dasharray:6 1.2 .6 1.2 .6 1.2}}
.mech{{stroke:#000;stroke-width:.2;fill:none;stroke-dasharray:.8 .6}}
.fr{{stroke:#000;stroke-width:.35;fill:none}}
.frb{{stroke:#000;stroke-width:.7;fill:none}}
.fill{{fill:#000;stroke:none}}
.efill{{fill:{GREEN};stroke:none}}
.hdr{{fill:#e8e8e8;stroke:#000;stroke-width:.2}}
text{{font-family:{FONT};fill:#000}}
.red{{fill:{RED}}}
.grn{{fill:{GREEN}}}
"""


def f(v, nd=2):
    """Format a number without trailing zeros."""
    if isinstance(v, int) or float(v).is_integer():
        return str(int(v))
    return f"{v:.{nd}f}".rstrip("0").rstrip(".")


def wrap(text, width, size):
    max_chars = max(8, int(width / (size * CHAR_W)))
    out, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if len(trial) > max_chars and line:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out or [""]


class Sheet:
    def __init__(self):
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, cls="ln"):
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="{cls}"/>')

    def poly(self, pts, cls="ln", closed=False):
        tag = "polygon" if closed else "polyline"
        d = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        self.add(f'<{tag} points="{d}" class="{cls}"/>')

    def rect(self, x, y, w, h, cls="ln"):
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" class="{cls}"/>')

    def circle(self, cx, cy, r, cls="ln"):
        self.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" class="{cls}"/>')

    def ellipse(self, cx, cy, rx, ry, cls="ln"):
        self.add(f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" class="{cls}"/>')

    def dot(self, x, y, cls="fill"):
        self.circle(x, y, 0.55, cls)

    def text(self, x, y, s, size=2.0, anchor="start", bold=False, cls=None, max_w=None, rotate=None):
        s = str(s)
        if max_w and len(s) * size * CHAR_W > max_w:
            size = max_w / (len(s) * CHAR_W)
        attrs = f'x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if bold:
            attrs += ' font-weight="bold"'
        if cls:
            attrs += f' class="{cls}"'
        if rotate is not None:
            attrs += f' transform="rotate({rotate} {x:.2f} {y:.2f})"'
        self.add(f"<text {attrs}>{escape(s)}</text>")

    def lines(self, x, y, rows, size=2.0, anchor="start", spacing=1.28, bold_first=False, cls=None, max_w=None):
        """Draw rows of text with the first baseline at y. Returns the y below the block."""
        for i, row in enumerate(rows):
            self.text(x, y + i * size * spacing, row, size, anchor, bold_first and i == 0, cls, max_w)
        return y + len(rows) * size * spacing

    def para(self, x, y, text, width, size=1.7, spacing=1.28, bold=False, cls=None):
        rows = wrap(text, width, size)
        for i, row in enumerate(rows):
            self.text(x, y + i * size * spacing, row, size, bold=bold, cls=cls)
        return y + len(rows) * size * spacing

    def svg(self):
        body = "\n".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" '
                f'viewBox="0 0 {W} {H}">\n<defs><style>{CSS}</style>'
                f'<marker id="arr" viewBox="0 0 4 4" refX="3.6" refY="2" markerWidth="1.3" markerHeight="1.3" '
                f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L4,2 L0,4 z" fill="#000"/></marker>'
                f'</defs>\n<rect width="{W}" height="{H}" fill="#fff"/>\n{body}\n</svg>\n')


# --- Symbols (IEC 60617 style) -------------------------------------------------------
# Each symbol is drawn in local coordinates with current flowing along +x and is
# placed with a rotation (0 = left-to-right, 90 = top-to-bottom). A symbol of
# half-length h spans local x in [-h, +h]; callers join symbol ends with lines.

def tf(cx, cy, rot):
    c, s = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))
    return lambda x, y: (cx + x * c - y * s, cy + x * s + y * c)


def seg(sh, T, a, b, cls="ln"):
    sh.line(*T(*a), *T(*b), cls)


def switch(sh, cx, cy, rot=0, kind="isolator", h=5.0, k=1.0):
    """Isolator (bar), circuit breaker (cross) or RCD (breaker + sensing toroid)."""
    T = tf(cx, cy, rot)
    a, b = -3.6 * k, 3.6 * k
    seg(sh, T, (-h, 0), (a, 0))
    seg(sh, T, (b, 0), (h, 0))
    seg(sh, T, (a, 0), (b - 0.6 * k, -3.0 * k))          # open blade
    if kind == "isolator":
        seg(sh, T, (b, -1.2 * k), (b, 1.2 * k))
    else:
        d = 0.9 * k
        seg(sh, T, (b - d, -d), (b + d, d))
        seg(sh, T, (b - d, d), (b + d, -d))
    if kind == "rcd":
        ex = a - 2.0
        x, y = T(ex, 0)
        rx, ry = (0.9, 2.0) if rot % 180 == 0 else (2.0, 0.9)
        sh.ellipse(x, y, rx, ry, "th")
        sh.poly([T(ex, -2.0), T(ex, -3.6), T(0, -3.6), T(0, -1.5)], "mech")


def fuse(sh, cx, cy, rot=0, h=5.0):
    T = tf(cx, cy, rot)
    seg(sh, T, (-h, 0), (h, 0))
    p = [T(-2.8, -1.0), T(2.8, -1.0), T(2.8, 1.0), T(-2.8, 1.0)]
    sh.poly(p, "ln", closed=True)


def spd(sh, cx, cy, rot=90, h=4.0):
    T = tf(cx, cy, rot)
    seg(sh, T, (-h, 0), (-2.5, 0))
    seg(sh, T, (2.5, 0), (h, 0))
    sh.poly([T(-2.5, -1.5), T(2.5, -1.5), T(2.5, 1.5), T(-2.5, 1.5)], "ln", closed=True)
    sh.poly([T(-1.8, 1.0), T(1.2, -1.0), T(2.0, -1.0)], "th")


def earth(sh, x, y, cls="es"):
    sh.line(x, y, x, y + 1.8, cls)
    for i, w in enumerate((4.0, 2.6, 1.2)):
        yy = y + 1.8 + i * 0.75
        sh.line(x - w / 2, yy, x + w / 2, yy, cls)


def padlock(sh, x, y):
    sh.rect(x - 0.9, y, 1.8, 1.3, "th")
    sh.add(f'<path d="M{x - 0.55:.2f},{y:.2f} v-0.5 a0.55,0.55 0 0 1 1.1,0 v0.5" class="th"/>')


def ticks(sh, x, y, n, vertical=False):
    for i in range(n):
        o = (i - (n - 1) / 2) * 0.9
        if vertical:
            sh.line(x - 1.1, y + o + 0.6, x + 1.1, y + o - 0.6, "th")
        else:
            sh.line(x + o - 0.6, y + 1.1, x + o + 0.6, y - 1.1, "th")


def pv_module(sh, cx, cy, w=9.0, h=5.0):
    x, y = cx - w / 2, cy - h / 2
    sh.rect(x, y, w, h, "ln")
    sh.line(x, y + h, x + w, y, "th")
    for i in range(2):
        ax = x - 3.4 + i * 1.6
        sh.add(f'<line x1="{ax:.2f}" y1="{y - 2.6:.2f}" x2="{ax + 2.0:.2f}" y2="{y - 0.6:.2f}" '
               f'class="th" marker-end="url(#arr)"/>')


# --- Sheet sections ----------------------------------------------------------------------

def draw_diagram(sh, d, p):
    phase, ac, inv, mod = d["phase"], d["ac"], d["inverter"], d["module"]
    n_ac = 2 if phase == 1 else 4
    y_main = 140.0

    sh.text(14, 16, "SINGLE LINE DIAGRAM - GRID-CONNECTED SOLAR PV SYSTEM", 3.2, bold=True)
    sh.text(14, 20.6, f"{d['supply_label']}   |   {d['array']['p_dc_kwp']:.2f} kWp DC / "
            f"{ac['p_ac_kw']:.2f} kWac   |   SOLAR ATAP - INDIRECT (BEHIND-THE-METER) CONNECTION", 2.0)
    if d["unverified"]:
        sh.text(312, 16, "PRELIMINARY - EQUIPMENT DATA NOT VERIFIED", 2.2, "end", True, "red")

    # PV strings -------------------------------------------------------------------------
    xs, gx, x = {}, {}, 32.0
    for gi, g in enumerate(d["mppts"]):
        x += 4 if gi else 0
        cxs = []
        for sid in g["strings"]:
            xs[sid] = x
            cxs.append(x)
            x += 15
        gx[g["mppt"]] = sum(cxs) / len(cxs)
    arr_l, arr_r = min(xs.values()) - 8, max(xs.values()) + 8
    sh.rect(arr_l, 26.5, arr_r - arr_l, 37, "box")
    sh.text(arr_l, 25.4, "PV ARRAY", 2.0, bold=True)
    strings = {s["id"]: s for s in d["strings"]}
    y_join = 100.0
    fuse_of = {g["mppt"]: g["fuse_a"] for g in d["mppts"]}
    for sid, cx in xs.items():
        s = strings[sid]
        sh.lines(cx, 29.6, [f"{sid} · MPPT {s['mppt']}", f"{s['modules']} × {f(mod['wattage_wp'])} Wp"],
                 1.55, "middle")
        ys = [38.5, 45.5, 57.5] if s["modules"] >= 3 else [38.5, 45.5][:s["modules"]]
        for i, cy in enumerate(ys):
            pv_module(sh, cx, cy)
            if i:
                prev = ys[i - 1]
                cls = "mech" if cy - prev > 8 else "ln"
                sh.line(cx, prev + 2.5, cx, cy - 2.5, cls)
        if s["modules"] >= 3:
            for k in range(3):
                sh.dot(cx + 3.2, 50.3 + k * 1.3)
        fa = fuse_of.get(s["mppt"])
        if fa:
            # String fuse in line (only where >= 3 strings are paralleled); no combiner box.
            sh.line(cx, ys[-1] + 2.5, cx, 85)
            fuse(sh, cx, 88, 90, 3)
            sh.text(cx + 1.6, 88.6, f"{fa}A", 1.3)
            sh.line(cx, 91, cx, y_join)
        else:
            sh.line(cx, ys[-1] + 2.5, cx, y_join)
        ticks(sh, cx, 71, 2, vertical=True)
        sh.text(cx + 1.6, 69.4, "+/-", 1.4)
    # Module frame bonding to the earth riser at x=16.
    sh.line(16, 45, arr_l, 45, "en")
    sh.line(16, 45, 16, 178, "en")
    sh.text(15.2, 112, f"{d['earth']['bond_mm2']} mm² G/Y Cu EARTH / BONDING CONDUCTOR", 1.5,
            "middle", cls="grn", rotate=-90)
    sh.text(arr_l - 0.5, 44.3, "FRAMES", 1.3, "end", cls="grn")

    # PV data block
    m0 = d["mppts"][0]
    alloc = ", ".join(f"{g['n_parallel']}×{g['n_series']} on MPPT {g['mppt']}" for g in d["mppts"])
    tx = arr_r + 6
    sh.lines(tx, 30, [
        f"PV ARRAY - {d['array']['p_dc_kwp']:.2f} kWp  ({d['array']['n_modules']} × {f(mod['wattage_wp'])} Wp)",
        f"{mod['brand']} {mod['model']}",
        f"{mod.get('technology', 'Monocrystalline')}, {f(mod['wattage_wp'])} Wp per module",
        f"Voc {f(mod['voc'])} V | Isc {f(mod['isc'])} A | Vmp {f(mod['vmp'])} V | Imp {f(mod['imp'])} A",
        f"Strings: {alloc}",
        f"String Voc {m0['voc_stc']:.0f} V ({max(g['voc_max'] for g in d['mppts']):.0f} V at {f(d['t_min'])} °C), "
        f"Isc {f(mod['isc'])} A",
        f"Frames bonded with {d['earth']['bond_mm2']} mm² G/Y Cu via stainless star washers / lugs",
    ], 1.9, bold_first=True)
    dc = d["dc_cable"]
    sh.lines(tx, 68.5, [
        "C1 - DC STRING CABLE (EACH STRING + AND -)",
        f"1C × {f(dc['size_mm2'])} mm² PV1-F XLPO Cu, 1.0/1.5 kV DC (EN 50618)",
        "(+) RED / (-) BLACK in heavy-duty UV-stabilised PVC or GI conduit",
        f"{f(dc['length_m'])} m one-way,  ΔV = {dc['vd_pct']:.2f} % (≤ {f(R.VD_DC_MAX_PCT)} %)",
    ], 1.7, bold_first=True)

    # Strings wired straight to the inverter DC inputs (no DC combiner box) -------------
    fuses = any(g["fuse_a"] for g in d["mppts"])
    for g in d["mppts"]:
        cxs = [xs[s] for s in g["strings"]]
        if len(cxs) > 1:
            sh.line(min(cxs), y_join, max(cxs), y_join)
            for cx in cxs:
                sh.dot(cx, y_join)
    fuse_txt = (f"STRING FUSES: gPV {max(g['fuse_a'] or 0 for g in d['mppts'])} A 1000 V DC in +/- of each string"
                if fuses else f"STRING FUSES: not required (< {R.STRING_FUSE_MIN_PARALLEL} parallel strings per MPPT)")
    sh.lines(arr_r + 6, 100, [
        "DC SWITCH & DC SPD: BUILT INTO INVERTER (NO DC COMBINER BOX)",
        fuse_txt,
    ], 1.75, bold_first=True)

    # Inverter -----------------------------------------------------------------------------
    n_m = len(d["mppts"])
    inv_x, inv_w, inv_y, inv_h = 21.0, 30.0, 126.0, 28.0
    for k, g in enumerate(d["mppts"]):
        c = gx[g["mppt"]]
        xin = inv_x + inv_w * (k + 1) / (n_m + 1)
        yb = 113.0 + k * 1.5
        sh.poly([(c, y_join), (c, yb), (xin, yb), (xin, inv_y)])
        sh.text(xin, inv_y + 2.4, f"M{g['mppt']}", 1.3, "middle")
    sh.rect(inv_x, inv_y, inv_w, inv_h, "hv")
    sh.line(inv_x, inv_y + inv_h, inv_x + inv_w, inv_y, "th")
    sh.text(inv_x + 7, inv_y + 12, "=", 4.5, "middle")
    sh.text(inv_x + inv_w - 7, inv_y + inv_h - 3.5, "~", 4.5, "middle")
    sh.text(inv_x + inv_w - 1, inv_y + 3.6, "INV", 1.5, "end", True)
    sh.line(16, inv_y + inv_h - 3, inv_x, inv_y + inv_h - 3, "en")
    sh.dot(16, inv_y + inv_h - 3, "efill")
    alloc = ", ".join(f"MPPT{g['mppt']}: {'+'.join(g['strings'])}" for g in d["mppts"])
    ac_v = "230 V 1-PHASE" if phase == 1 else "400 V 3-PHASE 4-WIRE"
    rows = [f"INV - {inv['brand']} {inv['model']}",
            f"Rated output {ac['p_ac_kw']:.2f} kWac, {ac_v}, 50 Hz",
            f"{inv['mppt_count']} MPPT ({alloc})",
            f"PF {inv.get('power_factor', '> 0.95')} | THD {inv.get('thd', '< 5 %')}"]
    compliance = inv.get("compliance", "MS IEC 62109-1/-2, IEEE 1547")
    if "island" not in compliance.lower():
        compliance += "; built-in anti-islanding"
    rows += wrap(compliance + "; integrated DC switch, DC SPD and AC SPD", 60, 1.7)
    sh.lines(18, 158.5, rows, 1.7, bold_first=True)

    # AC chain ------------------------------------------------------------------------------
    y = y_main
    x0 = inv_x + inv_w
    cab = ac["cable"]
    sh.line(x0, y, 96, y)
    ticks(sh, 86, y, n_ac)
    sh.lines(55, y + 4.5, ["C2 - AC CABLE",
                           *wrap(cab["spec"], 23, 1.45),
                           f"{f(cab['length_m'])} m, ΔV {cab['vd_pct']:.2f} %"], 1.45, bold_first=True)

    # Solar ACDB: MCB + PV meter (AC SPD is built into the inverter; no RCD, no AC isolator)
    bx, bw, by, bh = 96.0, 50.0, 122.0, 34.0
    sh.rect(bx, by, bw, bh, "box")
    sh.text(bx + 1.2, by + 3, "SOLAR ACDB (IP65)", 1.8, bold=True)
    mcb = ac["mcb"]
    switch(sh, 106, y, 0, "breaker")
    sh.lines(106, 129.5, ["MCB-S", f"{mcb['a']}A {mcb['poles']}", f"C {mcb['ka']}kA"], 1.45, "middle",
             bold_first=True)
    sh.line(111, y, 122, y)
    sh.rect(122, y - 4.5, 12, 9, "hv")
    sh.text(128, y + 0.4, "kWh", 2.4, "middle", True)
    sh.text(128, y + 3.3, "PV", 1.2, "middle")
    sh.lines(128, 129.5, ["PV METER", "(GENERATION)"], 1.45, "middle", bold_first=True)
    sh.line(134, y, bx + bw, y)
    sh.lines(bx + 1.2, y + 6, ["WARNING:", "DUAL SUPPLY - ISOLATE", "BOTH BEFORE SERVICING"], 1.45, cls="red")

    # Client / consumer DB: a single block (internal detail is the client's, not drawn)
    mx, mw, my, mh = 158.0, 50.0, 122.0, 34.0
    sh.line(bx + bw, y, mx, y)
    sh.text(152, y - 1.2, "C2", 1.35, "middle")
    ticks(sh, 152, y, n_ac)
    sh.rect(mx, my, mw, mh, "box")
    sh.text(mx + mw / 2, y + 0.9, "CLIENT / CONSUMER DB", 2.2, "middle", True)
    sh.line(mx + mw, y, 238, y)
    ticks(sh, 222, y, n_ac)

    # Earth: one protective earth cable (cable size only, no MET block / electrode description)
    sh.line(16, 178, 190, 178, "en")
    sh.text(24, 176.8, f"PROTECTIVE EARTH {f(d['earth']['pe_mm2'])} mm² G/Y Cu CABLE", 1.45, cls="grn")
    sh.line(mx + mw / 2, my + mh, mx + mw / 2, 178, "en")
    sh.dot(mx + mw / 2, 178, "efill")
    earth(sh, 190, 178)

    # Demarcation
    xd = 228.0
    sh.line(xd, 26, xd, 188, "dm")
    sh.text(xd - 2, 30, "◄ CONSUMER OWNERSHIP", 2.0, "end", True, "red")
    sh.text(xd + 2, 30, "TNB OWNERSHIP ►", 2.0, "start", True, "red")
    sh.text(xd - 1, 100, "DEMARCATION / OWNERSHIP BOUNDARY", 1.6, "middle", cls="red", rotate=-90)

    # TNB side: two blocks only - TNB kWh meter and TNB grid
    sh.rect(238, y - 8, 24, 16, "hv")
    sh.text(250, y + 0.9, "TNB kWh METER", 2.0, "middle", True)
    sh.line(262, y, 276, y)
    ticks(sh, 269, y, n_ac)
    sh.rect(276, y - 8, 30, 16, "hv")
    sh.text(291, y + 0.9, "TNB GRID", 2.2, "middle", True)


def schedule_rows(d, p):
    """Equipment schedule: TAG + DESCRIPTION only."""
    mod, inv, ac, dc = d["module"], d["inverter"], d["ac"], d["dc_cable"]
    ph = d["phase"]
    rows = [
        ("PV", f"PV MODULES - {d['array']['n_modules']} × {mod['brand']} {mod['model']}, {f(mod['wattage_wp'])} Wp "
               f"({d['array']['p_dc_kwp']:.2f} kWp)"),
        ("C1", f"DC STRING CABLE - 1C × {f(dc['size_mm2'])} mm² PV1-F XLPO Cu, {f(dc['length_m'])} m"),
    ]
    if any(g["fuse_a"] for g in d["mppts"]):
        fa = max(g["fuse_a"] or 0 for g in d["mppts"])
        rows.append(("SF", f"STRING FUSES - gPV {fa} A 1000 V DC, in + and - of each paralleled string"))
    rows += [
        ("INV", f"GRID-TIE INVERTER - {inv['brand']} {inv['model']}, {ac['p_ac_kw']:.2f} kWac, "
                f"{'230 V 1-ph' if ph == 1 else '400 V 3-ph'} 50 Hz (DC switch, DC SPD and AC SPD built in)"),
        ("C2", f"AC CABLE - {ac['cable']['spec']}, {f(ac['cable']['length_m'])} m"),
        ("ACDB", "SOLAR ACDB - IP65, warning \"DUAL SUPPLY - ISOLATE BOTH BEFORE SERVICING\""),
        ("MCB-S", f"SOLAR AC MCB - {ac['mcb']['a']} A {ac['mcb']['poles']}, Type C, {ac['mcb']['ka']} kA"),
        ("PVM", "PV METER - kWh meter for PV generation, inside the Solar ACDB"),
        ("DB", "CLIENT / CONSUMER DB - existing"),
        ("E", f"EARTHING - {f(d['earth']['pe_mm2'])} mm² G/Y Cu protective earth cable; "
              f"{d['earth']['bond_mm2']} mm² G/Y module bonding"),
        ("KWH", "TNB kWh METER - bi-directional smart meter, by TNB"),
        ("GRID", "TNB GRID"),
    ]
    return rows


def draw_schedule(sh, d, p):
    x0, y0 = 10.0, 191.0
    sh.text(12, y0 + 4.2, "EQUIPMENT SCHEDULE", 2.2, bold=True)
    cols = [("TAG", 14), ("DESCRIPTION", SCHED_W - 14)]
    rows = schedule_rows(d, p)
    rh = min(4.4, (286.0 - (y0 + 10.5)) / len(rows))
    yh = y0 + 6
    sh.rect(x0, yh, SCHED_W, 4.5, "hdr")
    x = x0
    for name, w in cols:
        sh.text(x + 1, yh + 3.2, name, 1.7, bold=True)
        x += w
    y = yh + 4.5
    for r in rows:
        x = x0
        for i, (name, w) in enumerate(cols):
            sh.text(x + 1, y + rh * 0.7, r[i], 1.6, bold=(i == 0), max_w=w - 2)
            x += w
        y += rh
        sh.line(x0, y, x0 + SCHED_W, y, "th")
    x = x0
    for _, w in cols[:-1]:
        x += w
        sh.line(x, yh, x, y, "th")


def check_rows(d):
    inv, ac, ph = d["inverter"], d["ac"], d["phase"]
    voc_max = max(g["voc_max"] for g in d["mppts"])
    vmp_min = min(g["vmp_min"] for g in d["mppts"])
    isc = max(g["isc_total"] for g in d["mppts"])
    cap = R.CAP_KW[ph]
    return [
        (f"Voc,max @ {f(d['t_min'])} °C", f"{voc_max:.0f} V", f"< {inv['max_dc_voltage_v']} V",
         voc_max < inv["max_dc_voltage_v"]),
        (f"Vmp,min @ {f(d['t_max'])} °C", f"{vmp_min:.0f} V", f"≥ {inv['mppt_voltage_min_v']} V",
         vmp_min >= inv["mppt_voltage_min_v"]),
        ("Isc per MPPT", f"{isc:.2f} A", f"≤ {inv['max_isc_per_mppt_a']} A", isc <= inv["max_isc_per_mppt_a"]),
        ("ΔV DC", f"{d['dc_cable']['vd_pct']:.2f} %", f"≤ {f(R.VD_DC_MAX_PCT)} %",
         d["dc_cable"]["vd_pct"] <= R.VD_DC_MAX_PCT),
        ("ΔV AC", f"{ac['cable']['vd_pct']:.2f} %", f"≤ {f(R.VD_AC_MAX_PCT)} %",
         ac["cable"]["vd_pct"] <= R.VD_AC_MAX_PCT),
        ("ΔV total", f"{d['vd_total_pct']:.2f} %", f"≤ {f(R.VD_TOTAL_MAX_PCT)} %",
         d["vd_total_pct"] <= R.VD_TOTAL_MAX_PCT),
        ("DC/AC ratio", f"{d['array']['dc_ac_ratio']:.2f}", f"{R.DC_AC_RATIO_MIN}-{R.DC_AC_RATIO_MAX}",
         R.DC_AC_RATIO_MIN <= d["array"]["dc_ac_ratio"] <= R.DC_AC_RATIO_MAX),
        ("ATAP cap (AC)", f"{ac['p_ac_kw']:.2f} kW", f"≤ {f(cap)} kW", ac["p_ac_kw"] <= cap),
    ]


def table(sh, x, y, title, header, rows, widths, rh=4.3, size=1.55):
    total = sum(widths)
    sh.rect(x, y, total, 5, "hdr")
    sh.text(x + total / 2, y + 3.5, title, 1.85, "middle", True, max_w=total - 2)
    y += 5
    cx = x
    for h, w in zip(header, widths):
        sh.text(cx + 1, y + 3.0, h, 1.5, bold=True, max_w=w - 2)
        cx += w
    y += 4.2
    sh.line(x, y, x + total, y, "th")
    for r in rows:
        cx = x
        for i, (v, w) in enumerate(zip(r, widths)):
            cls = None
            if v == "OK":
                cls = "grn"
            elif v == "FAIL":
                cls = "red"
            sh.text(cx + 1, y + rh * 0.72, v, size, bold=v in ("OK", "FAIL"), cls=cls, max_w=w - 2)
            cx += w
        y += rh
        sh.line(x, y, x + total, y, "th")
    top = y - rh * len(rows) - 4.2
    cx = x
    for w in widths[:-1]:
        cx += w
        sh.line(cx, top, cx, y, "th")
    sh.rect(x, top - 5, total, y - top + 5, "fr")
    return y


def stamp_block(sh, x, y, w, title, rows, stamp_label):
    h = 36.0
    sh.rect(x, y, w, h, "fr")
    sh.rect(x, y, w, 5, "hdr")
    sh.text(x + w / 2, y + 3.5, title, 1.8, "middle", True, max_w=w - 2)
    yy = y + 9
    for label, value in rows:
        sh.text(x + 1.5, yy, label, 1.55, bold=True)
        sh.text(x + 36, yy, value or "__________________", 1.55, max_w=w - 37)
        yy += 4.1
    sh.text(x + 1.5, y + h - 7, "Signature: ____________________", 1.55)
    sh.text(x + 1.5, y + h - 2.5, "Date:  ___ / ___ / ______", 1.55)
    sh.rect(x + w - 24, y + 22.5, 22, 12, "box")
    sh.text(x + w - 13, y + 29.3, stamp_label, 1.4, "middle")


def draw_endorsements(sh, d, p):
    """QP and CP endorsement blocks, bottom of the diagram frame, right of the schedule."""
    people = p["people"]
    y, w = 197.0, 70.0
    stamp_block(sh, 172.0, y, w, "SEDA MALAYSIA QUALIFIED PERSON (QP)", [
        ("Qualified Person Name:", people.get("qp_name")),
        ("SEDA GCPV Cert. No.:", people.get("qp_cert_no")),
        ("Registered Svc Provider:", people.get("rpvsp")),
    ], "OFFICIAL QP STAMP")
    stamp_block(sh, 245.0, y, w, "ST REGISTERED COMPETENT PERSON", [
        ("Competent Person Name:", people.get("cp_name")),
        ("Category:", people.get("cp_category") or "PW4 / A0 / PEPC"),
        ("ST Competency Cert. No.:", people.get("cp_cert_no")),
        ("ST Contractor Reg. (Form Q):", people.get("contractor_reg_no")),
    ], "OFFICIAL ST STAMP")


def draw_side(sh, d, p):
    x, w = 318.0, 90.0
    prot = [(a, b, c) for a, b, c in R.PROTECTION_SETTINGS]
    y = table(sh, x, 12, "TNB MANDATORY INVERTER PROTECTION SETTINGS", ["PARAMETER FUNCTION",
              "TRIP VOLTAGE / FREQUENCY", "CLEARING"], prot, [34, 36, 20], 4.1)
    checks = [(a, b, c, "OK" if ok else "FAIL") for a, b, c, ok in check_rows(d)]
    y = table(sh, x, y + 3, "DESIGN VERIFICATION", ["CHECK", "RESULT", "LIMIT", ""], checks, [32, 22, 24, 12], 3.9)

    notes = [
        f"Installation to {', '.join(R.GOVERNING_STANDARDS[:4])}; symbols to IEC 60617.",
        "Indirect (behind-the-meter) connection: PV feeds the client / consumer DB; "
        "TNB meter is bi-directional.",
        "All exposed metalwork bonded with the protective earth cable.",
        "Warning labels at consumer DB, ACDB, meter and inverter: \"DUAL SUPPLY - ISOLATE BOTH BEFORE SERVICING\".",
        "Inverter protection settings per TNB table above; to be tested and recorded at commissioning "
        "(MS IEC 62446).",
        "Cable lengths and existing DB arrangement to be verified on site.",
    ]
    y += 3
    sh.text(x, y + 2, "GENERAL NOTES", 1.9, bold=True)
    y += 4.6
    for i, n in enumerate(notes, 1):
        sh.text(x, y, f"{i}.", 1.5)
        y = sh.para(x + 3, y, n, w - 3, 1.5, 1.25) + 0.5
    top = title_column(sh, d, p, x, w, 285.0)
    draw_legend(sh, x, y + 1.5, w, top - 2)


def draw_legend(sh, x, y, w, y_max):
    items = [
        ("PV MODULE", lambda cx, cy: pv_module(sh, cx + 1, cy, 7, 3.6)),
        ("SWITCH-DISCONNECTOR", lambda cx, cy: switch(sh, cx, cy, 0, "isolator", 4.5, 0.75)),
        ("CIRCUIT BREAKER (MCB)", lambda cx, cy: switch(sh, cx, cy, 0, "breaker", 4.5, 0.75)),
        ("FUSE", lambda cx, cy: fuse(sh, cx, cy, 0, 4.5)),
        ("EARTH", lambda cx, cy: earth(sh, cx, cy - 2)),
        ("EARTH CONDUCTOR", lambda cx, cy: sh.line(cx - 4.5, cy, cx + 4.5, cy, "en")),
        ("ENCLOSURE / BOARD", lambda cx, cy: sh.rect(cx - 4.5, cy - 1.8, 9, 3.6, "box")),
        ("OWNERSHIP BOUNDARY", lambda cx, cy: sh.line(cx - 4.5, cy, cx + 4.5, cy, "dm")),
        ("No. OF CONDUCTORS", lambda cx, cy: (sh.line(cx - 4.5, cy, cx + 4.5, cy), ticks(sh, cx, cy, 4))),
    ]
    rows = (len(items) + 1) // 2
    rh = min(5.2, (y_max - y - 6) / rows)
    rh = max(rh, 3.0)
    sh.text(x, y + 2, "LEGEND", 1.9, bold=True)
    for i, (label, draw) in enumerate(items):
        cx = x + 6 + (i % 2) * (w / 2)
        cy = y + 6.5 + (i // 2) * rh
        draw(cx, cy)
        sh.text(cx + 7, cy + 0.6, label, 1.4, max_w=w / 2 - 14)


# Integrator details printed in the title block when the project does not give its own.
DEFAULT_INTEGRATOR = ("Eternalgy Sdn. Bhd.", "21-01, Jln Mutiara Emas 10 / 19, Tmn Mount Austin, 81100 Johor Bahru")


def nice_date(v):
    """2026-11-19 -> 19 November 2026. Anything else is printed as given."""
    try:
        from datetime import datetime
        dt = datetime.strptime(str(v).strip(), "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%B %Y')}"
    except (ValueError, TypeError):
        return str(v or "").strip()


def title_column(sh, d, p, x, w, y_bottom):
    """Title block, top to bottom as on the Eternalgy sheets: copyright note, revision table,
    PV module summary, logo, client, integrator, project title, drawing title, data grid.
    Anchored to y_bottom; returns the y of its top edge. Never raises on missing data."""
    pr, mod = p["project"], d["module"]
    tx = x + 2.0
    inner = w - 4.0
    try:
        from .pe import address_lines, logo_data_uri
        uri = logo_data_uri()
    except Exception:                      # logo / helper unavailable: text fallback, sheet still made
        uri, address_lines = None, None

    def addr_rows(text, width, size):
        rows = address_lines(text, width) if address_lines else wrap(text, width, size)
        return rows or []

    def label(y, t):
        sh.text(tx, y + 2.2, t, 1.1, bold=True)

    secs = []   # (height, draw(y0))

    def copyright_(y0):
        sh.text(tx, y0 + 3.6, "THIS DRAWING IS COPYRIGHT PROTECTED", 1.5)
        for i, t in enumerate(["CONTRACTORS MUST CHECK ALL DIMENSIONS ON", "SITE . ONLY FIGURED",
                               "DIMENSIONS ARE TO BE WORKED. DISCREPANCIES", "MUST BE REPORTED IMMEDIATELY TO",
                               "ARCHITECT/ENGINEER BEFROE PROCEEDING."]):
            sh.text(tx, y0 + 7.6 + i * 1.7, t, 1.3, max_w=inner)
    secs.append((16.0, copyright_))

    def revisions(y0):
        sh.rect(tx, y0 + 1.5, inner, 12.0, "fr")
        sh.line(tx, y0 + 4.7, tx + inner, y0 + 4.7, "th")
        sh.line(tx + 6, y0 + 1.5, tx + 6, y0 + 13.5, "th")
        sh.line(tx + 17, y0 + 1.5, tx + 17, y0 + 13.5, "th")
        sh.text(tx + 1.2, y0 + 4.0, "NO", 1.2)
        sh.text(tx + 7.2, y0 + 4.0, "TARIKH", 1.2)
    secs.append((15.0, revisions))

    lines = [f"{str(mod.get('brand', '')).upper()} PV MODULE".strip(),
             f"{mod.get('model', '')} X {d['array']['n_modules']} NOS", ""]
    for i, st in enumerate(d["strings"], 1):
        lines.append(f"STRING {i}: {f(mod['wattage_wp'])}W x {st['modules']} NOS")

    def summary(y0):
        for i, t in enumerate(lines):
            sh.text(tx, y0 + 4.6 + i * 3.0, t, 2.1, max_w=inner)
    secs.append((3.0 + 3.0 * len(lines) + 2.0, summary))

    def logo(y0):
        sh.add(f'<rect x="{tx:.2f}" y="{y0 + 1.5:.2f}" width="{inner:.2f}" height="10" fill="#1d1d1b"/>')
        if uri:
            lw = inner - 10
            lh = lw * 85 / 640
            sh.add(f'<image x="{tx + 5:.2f}" y="{y0 + 6.5 - lh / 2:.2f}" width="{lw:.2f}" height="{lh:.2f}" '
                   f'href="{uri}"/>')
        else:
            sh.add(f'<text x="{x + w / 2:.2f}" y="{y0 + 8.2:.2f}" font-size="3" text-anchor="middle" '
                   f'font-weight="bold" fill="#fff">ETERNALGY</text>')
    secs.append((13.0, logo))

    cname = wrap(pr.get("account_holder", ""), inner, 2.4) if pr.get("account_holder") else []
    caddr = addr_rows(pr.get("address", ""), inner, 2.0)

    def client(y0):
        label(y0, "Client :-")
        yy = y0 + 6.2
        for t in cname:
            sh.text(tx, yy, t, 2.4, max_w=inner)
            yy += 3.1
        yy += 1.6
        for t in caddr:
            sh.text(tx, yy, t, 2.0, max_w=inner)
            yy += 2.6
    secs.append((max(16.0, 9.0 + 3.1 * len(cname) + 1.6 + 2.6 * len(caddr)), client))

    iname = pr.get("integrator_name") or DEFAULT_INTEGRATOR[0]
    iaddr = addr_rows(pr.get("integrator_address") or DEFAULT_INTEGRATOR[1], inner, 1.9)

    def integrator(y0):
        label(y0, "Solar System Integrator :-")
        sh.text(tx, y0 + 6.6, iname, 2.3, max_w=inner)
        for i, t in enumerate(iaddr):
            sh.text(tx, y0 + 10.6 + i * 2.5, t, 1.9, max_w=inner)
    secs.append((12.0 + 2.5 * len(iaddr), integrator))

    kwp = d["array"]["p_dc_kwp"]

    def project(y0):
        label(y0, "Project Title :-")
        sh.text(x + w / 2, y0 + 7.4, pr.get("project_title") or f"{f(round(kwp, 2))}kWp Solar System",
                2.6, "middle", max_w=inner)
    secs.append((10.0, project))

    def drawing(y0):
        label(y0, "Drawing Title :-")
        sh.text(x + w / 2, y0 + 7.4, pr.get("drawing_title") or "Single Line Diagram", 2.6, "middle", max_w=inner)
    secs.append((10.0, drawing))

    def grid(y0):
        rows = [("Drawn By", pr.get("drawn_by", "")), ("Approved By", pr.get("approved_by", "")),
                ("Date", nice_date(pr.get("date", ""))), ("Scale", "NTS"), ("Revision", pr.get("revision", ""))]
        rh, mid = 2.9, x + 46
        for i, (k, v) in enumerate(rows):
            sh.text(x + 1.5, y0 + 2.1 + i * rh, f"{k} :- {v}".rstrip(), 1.2, max_w=mid - x - 2.5)
            if i:
                sh.line(x, y0 + i * rh, mid, y0 + i * rh, "th")
        sh.line(mid, y0, mid, y0 + rh * len(rows), "th")
        sh.line(mid, y0 + rh * 2, x + w, y0 + rh * 2, "th")
        sh.line(mid, y0 + rh * 3, x + w, y0 + rh * 3, "th")
        sh.text(mid + 1.2, y0 + rh * 2 + 2.1, f"Drawing No :- {pr.get('drawing_no', '')}", 1.2, max_w=x + w - mid - 2)
    secs.append((2.9 * 5 + 0.5, grid))

    total = sum(h for h, _ in secs)
    top = y_bottom - total
    y = top
    for i, (h, draw) in enumerate(secs):
        try:
            draw(y)
        except Exception:                  # one bad field must not blank the rest of the block
            sh.text(tx, y + 4, "(title block entry could not be drawn)", 1.2, cls="red")
        y += h
        if i < len(secs) - 1:
            sh.line(x, y, x + w, y, "fr")
    sh.rect(x, top, w, total, "frb")
    return top


def render(d, p):
    sh = Sheet()
    sh.rect(10, 10, 400, 277, "frb")
    sh.line(316, 10, 316, 287, "fr")
    sh.line(10, 191, 316, 191, "fr")
    draw_diagram(sh, d, p)
    draw_schedule(sh, d, p)
    draw_endorsements(sh, d, p)
    draw_side(sh, d, p)
    if d["issues"].errors:
        sh.add(f'<text x="163" y="110" font-size="13" text-anchor="middle" font-weight="bold" fill="{RED}" '
               f'fill-opacity="0.22" transform="rotate(-18 163 110)">DESIGN CHECK FAILED - NOT FOR SUBMISSION</text>')
    return sh.svg()
