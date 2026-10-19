"""Render a complete A3-landscape SLD sheet as SVG. All units are millimetres.

Sheet zones:
  diagram      x 10-316, y 10-191   L-shaped flow: PV (top-left) down to the
                                    inverter, then AC left-to-right to the TNB grid
  schedule     x 10-316, y 191-287  equipment schedule with full specifications
  side column  x 316-410            protection settings, design checks, notes,
                                    QP / CP endorsement blocks, title block
"""

import math
from xml.sax.saxutils import escape

from . import rules as R

W, H = 420, 297
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
    y_cb = 82.0
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
        sh.line(cx, ys[-1] + 2.5, cx, y_cb)
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

    # DC combiner / isolator box -------------------------------------------------------
    cb_l, cb_r, cb_b = arr_l, arr_r, 118.0
    sh.rect(cb_l, y_cb, cb_r - cb_l, cb_b - y_cb, "box")
    sh.text(cb_l + 1, y_cb + 2.6, "DCB", 1.5, bold=True)
    y_iso, y_tap, y_bar = 99.0, 106.0, 115.5
    fuses = any(g["fuse_a"] for g in d["mppts"])
    for g in d["mppts"]:
        m, cxs = g["mppt"], [xs[s] for s in g["strings"]]
        top = y_cb
        for cx in cxs:
            if g["fuse_a"]:
                fuse(sh, cx, 87, 90, 3)
                sh.text(cx + 1.6, 87.6, f"{g['fuse_a']}A", 1.3)
                sh.line(cx, 90, cx, 92)
            else:
                sh.line(cx, top, cx, 92)
        if len(cxs) > 1:
            sh.line(min(cxs), 92, max(cxs), 92)
            for cx in cxs:
                sh.dot(cx, 92)
        c = gx[m]
        sh.line(c, 92, c, y_iso - 5)
        switch(sh, c, y_iso, 90, "isolator")
        sh.text(c + 2.4, y_iso + 5.3, f"DCI-{m}" if len(d["mppts"]) > 1 else "DCI", 1.3)
        sh.line(c, y_iso + 5, c, cb_b)
        sh.dot(c, y_tap)
        sh.line(c, y_tap, c - 5, y_tap)
        spd(sh, c - 5, y_tap + 4.5, 90, 4.5)
        sh.text(c - 7.2, y_tap + 4.0, "SPD", 1.2, "end")
        sh.line(c - 5, y_tap + 9, c - 5, y_bar, "es")
    if len(d["mppts"]) > 1:
        sh.line(gx[d["mppts"][0]["mppt"]] + 1.7, y_iso - 0.4, gx[d["mppts"][-1]["mppt"]] + 1.7, y_iso - 0.4, "mech")
    right_spd = max(gx.values()) - 5
    sh.line(cb_l, y_bar, right_spd, y_bar, "es")
    sh.line(16, y_bar, cb_l, y_bar, "en")
    sh.dot(16, y_bar, "efill")

    iso, dspd = d["dc_isolator"], d["dc_spd"]
    fuse_txt = (f"STRING FUSES: gPV {max(g['fuse_a'] or 0 for g in d['mppts'])} A 1000 V DC in +/- of each string"
                if fuses else f"STRING FUSES: not required (< {R.STRING_FUSE_MIN_PARALLEL} parallel strings per MPPT)")
    sh.lines(cb_r + 6, 87, [
        "DC COMBINER / ISOLATOR BOX (DCB) - IP65 OUTDOOR",
        f"DCI: {iso['poles']}-POLE DC ISOLATOR {iso['voltage_v']} V DC {iso['current_a']} A, {iso['utilisation']}, "
        f"IP65, LOCKABLE IN OFF",
        '      Label: "DC ISOLATOR - LOCKABLE"',
        f"SPD: TYPE II DC SPD, Ucpv {dspd['ucpv_v']} V, In {dspd['in_ka']} kA, Imax {dspd['imax_ka']} kA "
        f"(MS IEC 61643-12), one per MPPT",
        "      bonded to earth bar by shortest path (< 0.5 m)",
        fuse_txt,
    ], 1.75, bold_first=True)

    # Inverter -----------------------------------------------------------------------------
    n_m = len(d["mppts"])
    inv_x, inv_w, inv_y, inv_h = 21.0, 30.0, 126.0, 28.0
    for k, g in enumerate(d["mppts"]):
        c = gx[g["mppt"]]
        xin = inv_x + inv_w * (k + 1) / (n_m + 1)
        yb = 119.4 + k * 1.5
        sh.poly([(c, cb_b), (c, yb), (xin, yb), (xin, inv_y)])
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
    rows += wrap(compliance + ("; integrated DC switch" if inv.get("integrated_dc_switch") else ""), 60, 1.7)
    sh.lines(18, 158.5, rows, 1.7, bold_first=True)

    # AC chain ------------------------------------------------------------------------------
    y = y_main
    x0 = inv_x + inv_w
    aci = ac["isolator"]
    sh.line(x0, y, 59, y)
    ticks(sh, 54, y, n_ac)
    switch(sh, 64, y, 0, "isolator")
    padlock(sh, 67.6, y - 7.2)
    sh.lines(64, 127.8, ["ACI", f"{aci['a']}A {aci['poles']}P", aci["utilisation"]], 1.5, "middle", bold_first=True)
    cab = ac["cable"]
    sh.line(69, y, 96, y)
    ticks(sh, 82, y, n_ac)
    sh.lines(71, y + 4.5, ["C2 - AC CABLE",
                           *wrap(cab["spec"], 23, 1.45),
                           f"{f(cab['length_m'])} m, ΔV {cab['vd_pct']:.2f} %"], 1.45, bold_first=True)

    # Solar ACDB
    bx, bw, by, bh = 96.0, 50.0, 122.0, 44.0
    sh.rect(bx, by, bw, bh, "box")
    sh.text(bx + 1.2, by + 3, "SOLAR ACDB (IP65)", 1.8, bold=True)
    mcb, rcd, aspd = ac["mcb"], ac["rcd"], ac["spd"]
    switch(sh, 106, y, 0, "breaker")
    sh.lines(106, 129.5, ["MCB-S", f"{mcb['a']}A {mcb['poles']}", f"C {mcb['ka']}kA"], 1.45, "middle",
             bold_first=True)
    sh.line(111, y, 116, y)
    switch(sh, 123, y, 0, "rcd", h=7)
    sh.lines(124, 129.5, ["RCD-S", f"{rcd['a']}A {rcd['poles']}P {rcd['ma']}mA", rcd["type"].upper()], 1.45,
             "middle", bold_first=True)
    sh.line(130, y, bx + bw, y)
    sh.dot(139, y)
    switch(sh, 139, y + 6.5, 90, "breaker", h=4.5, k=0.7)
    spd(sh, 139, y + 15, 90, 4)
    sh.lines(136.5, y + 6, [f"{aspd['backup_a']}A"], 1.35, "end")
    sh.lines(136.5, y + 13.2, ["AC SPD", "TYPE II", f"{aspd['poles']}P Uc {aspd['uc_v']}V", f"In {aspd['in_ka']}kA"],
             1.35, "end")
    sh.line(139, y + 19, 139, 178, "en")
    sh.lines(bx + 1.2, y + 6, ["WARNING:", "DUAL SUPPLY - ISOLATE", "BOTH BEFORE SERVICING"], 1.45, cls="red")

    # Consumer MDB
    mx, mw, my, mh = 158.0, 60.0, 122.0, 50.0
    sh.line(bx + bw, y, 163, y)
    sh.text(152, y - 1.2, "C2", 1.35, "middle")
    ticks(sh, 152, y, n_ac)
    sh.rect(mx, my, mw, mh, "box")
    sh.text(mx + 1.2, my + 3, "CONSUMER MDB - PCC", 1.8, bold=True)
    mdb = d["mdb"]
    switch(sh, 168, y, 0, "breaker")
    sh.lines(168, 129.5, ["SOLAR PV", "FEED", f"{mdb['solar_way_a']}A {mdb['solar_way_poles']}"], 1.45, "middle",
             bold_first=True)
    circuits = mdb["circuits"][:5]
    step = 6.0 if len(circuits) <= 4 else 5.0
    bus_top, bus_bot = y - 4, y + 6 + step * (len(circuits) - 1) + 1.5
    sh.line(173, y, 180, y)
    sh.line(180, bus_top, 180, bus_bot, "bus")
    for i, c in enumerate(circuits):
        yy = y + 6 + i * step
        sh.line(180, yy, 186, yy)
        switch(sh, 189.5, yy, 0, "breaker", h=3.5, k=0.6)
        sh.add(f'<line x1="193" y1="{yy:.2f}" x2="197.5" y2="{yy:.2f}" class="ln" marker-end="url(#arr)"/>')
        sh.text(198.5, yy + 0.5, f"{c['rating_a']}A {c['name']}", 1.4, max_w=19)
    sh.line(180, y, 185, y)
    switch(sh, 192, y, 0, "rcd", h=7)
    sh.lines(192, 129.5, ["RCCB", f"{mdb['main_rcd_a']}A {mdb['main_rcd_ma']}mA"], 1.45, "middle", bold_first=True)
    sh.line(199, y, 204, y)
    switch(sh, 209, y, 0, "isolator")
    sh.lines(209.5, 129.5, ["MAIN SW", f"{mdb['main_switch_a']}A {mdb['main_switch_poles']}"], 1.45, "middle",
             bold_first=True)
    sh.line(214, y, 238, y)
    ticks(sh, 222, y, n_ac)

    # Earth bus, MET and electrode
    sh.line(16, 178, 176, 178, "en")
    sh.text(24, 176.8, f"PROTECTIVE EARTH {d['earth']['pe_mm2']} mm² G/Y Cu TO MAIN EARTH TERMINAL (MET)", 1.45,
            cls="grn")
    sh.rect(176, 175.5, 14, 5, "es")
    sh.text(183, 178.9, "MET", 1.6, "middle", True, "grn")
    sh.line(183, my + mh, 183, 175.5, "en")
    sh.line(190, 178, 195, 178, "es")
    earth(sh, 195, 178)
    sh.lines(198, 180.4, ["EARTH ELECTRODE (TT SYSTEM)", "16 mm Ø × 2.4 m Cu-bonded steel rod",
                          f"R earth < {R.EARTH_RESISTANCE_MAX_OHM} Ω"], 1.4, cls="grn")

    # Demarcation
    xd = 228.0
    sh.line(xd, 26, xd, 188, "dm")
    sh.text(xd - 2, 30, "◄ CONSUMER OWNERSHIP", 2.0, "end", True, "red")
    sh.text(xd + 2, 30, "TNB OWNERSHIP ►", 2.0, "start", True, "red")
    sh.text(xd - 1, 100, "DEMARCATION / OWNERSHIP BOUNDARY", 1.6, "middle", cls="red", rotate=-90)

    # TNB meter, cut-out, grid
    tnb = d["tnb"]
    sh.rect(238, y - 4.5, 12, 9, "hv")
    sh.text(244, y + 0.4, "kWh", 2.4, "middle", True)
    sh.text(244, y + 3.3, "IMP ⇄ EXP", 1.2, "middle")
    sh.lines(244, 124.5, ["KWH", "TNB BI-DIRECTIONAL", "SMART METER (kWh)", tnb["meter"],
                          "IMPORT & EXPORT REGISTERS"], 1.4, "middle", bold_first=True)
    sh.line(250, y, 263, y)
    sh.rect(260, y - 6, 16, 18, "box")
    fuse(sh, 268, y, 0, 5)
    sh.circle(265.5, y + 7.5, 0.6, "ln")
    sh.circle(270.5, y + 7.5, 0.6, "ln")
    sh.line(266.1, y + 7.5, 269.9, y + 7.5, "hv")
    sh.text(268, y + 10.6, "N LINK", 1.25, "middle")
    sh.lines(268, 124.5, ["CO", "TNB CUT-OUT", f"{tnb['cutout_a']}A HRC FUSE", "+ NEUTRAL LINK", "(SEALED BY TNB)"],
             1.4, "middle", bold_first=True)
    sh.line(273, y, 295.5, y)
    ticks(sh, 284, y, n_ac)
    sh.lines(276.5, y + 4.5, ["SERVICE CABLE", *wrap(tnb["service_cable"], 18, 1.35)], 1.35)
    sh.circle(300, y, 4.5, "hv")
    sh.text(300, y + 1.5, "~", 4.5, "middle")
    sh.lines(300, y - 12, ["TNB LV", "NETWORK", "400/230 V" if phase == 3 else "230 V", "50 Hz"], 1.45, "middle",
             bold_first=True)


def schedule_rows(d, p):
    mod, inv, ac, dc = d["module"], d["inverter"], d["ac"], d["dc_cable"]
    iso, dspd, mdb, tnb = d["dc_isolator"], d["dc_spd"], d["mdb"], d["tnb"]
    m_isc = max(g["isc_total"] for g in d["mppts"])
    voc_max = max(g["voc_max"] for g in d["mppts"])
    voc_stc = max(g["voc_stc"] for g in d["mppts"])
    ph = d["phase"]
    rows = [
        ("PV", "PV MODULES", f"{d['array']['n_modules']} × {mod['brand']} {mod['model']}, {f(mod['wattage_wp'])} Wp "
         f"{mod.get('technology', '')}, Voc {f(mod['voc'])} V, Isc {f(mod['isc'])} A, Vmp {f(mod['vmp'])} V, "
         f"Imp {f(mod['imp'])} A", f"Pdc = {d['array']['n_modules']} × {f(mod['wattage_wp'])} W = "
         f"{d['array']['p_dc_kwp']:.2f} kWp"),
        ("C1", "DC STRING CABLE", f"1C × {f(dc['size_mm2'])} mm² PV1-F XLPO Cu 1.0/1.5 kV DC (EN 50618), red (+) / "
         f"black (-), UV-PVC / GI conduit, {f(dc['length_m'])} m",
         f"Iz {dc['iz_a']:.1f} A ≥ 1.25 × Isc = {1.25 * mod['isc']:.1f} A; ΔV {dc['vd_pct']:.2f} % ≤ 1.0 %"),
    ]
    if any(g["fuse_a"] for g in d["mppts"]):
        fa = max(g["fuse_a"] or 0 for g in d["mppts"])
        rows.append(("SF", "STRING FUSES", f"gPV {fa} A 1000 V DC fuse in + and - of each paralleled string",
                     f"I fuse ≥ 1.25 × Isc = {1.25 * mod['isc']:.1f} A; ≤ module max series fuse"))
    rows += [
        ("DCI", "DC ISOLATOR", f"{iso['poles']}-pole {iso['voltage_v']} V DC {iso['current_a']} A, "
         f"{iso['utilisation']}, IP65, lockable, label \"DC ISOLATOR - LOCKABLE\"",
         f"≥ 1.25 × Isc,mppt = {1.25 * m_isc:.1f} A; ≥ Voc,max {voc_max:.0f} V"),
        ("DSPD", "DC SURGE PROTECTION", f"Type II DC SPD, Ucpv {dspd['ucpv_v']} V, In {dspd['in_ka']} kA, "
         f"Imax {dspd['imax_ka']} kA, MS IEC 61643-12, one per MPPT",
         f"Ucpv ≥ 1.2 × Voc = {1.2 * voc_stc:.0f} V"),
        ("INV", "GRID-TIE INVERTER", f"{inv['brand']} {inv['model']}, {ac['p_ac_kw']:.2f} kWac, "
         f"{'230 V 1-ph' if ph == 1 else '400 V 3-ph'} 50 Hz, {inv['mppt_count']} MPPT, PF "
         f"{inv.get('power_factor', '> 0.95')}, THD {inv.get('thd', '< 5 %')}",
         f"Voc,max {voc_max:.0f} V < {inv['max_dc_voltage_v']} V; Isc {m_isc:.2f} A ≤ {inv['max_isc_per_mppt_a']} A"),
        ("C2", "AC CABLE", f"{ac['cable']['spec']}, inverter → ACDB → MDB, {f(ac['cable']['length_m'])} m total",
         f"Iz {f(ac['cable']['iz_a'])} A ≥ In {ac['mcb']['a']} A; ΔV {ac['cable']['vd_pct']:.2f} % ≤ 1.0 %"),
        ("ACI", "AC ISOLATOR", f"{ac['isolator']['a']} A {ac['isolator']['poles']}-pole, "
         f"{ac['isolator']['utilisation']}, lockable, label \"SOLAR PV AC ISOLATOR - LOCKABLE\"",
         f"≥ 1.25 × Iac = {ac['mcb_min']:.1f} A"),
        ("ACDB", "SOLAR AC DB", "\"SOLAR AC DISTRIBUTION BOARD (ACDB)\", IP55 indoor / IP65 outdoor, "
         "warning \"DUAL SUPPLY - ISOLATE BOTH BEFORE SERVICING\"", "Dedicated sub-board before tie-in"),
        ("MCB-S", "SOLAR AC MCB", f"{ac['mcb']['a']} A {ac['mcb']['poles']}, Type C curve, Icu {ac['mcb']['ka']} kA",
         f"Iac,max {ac['i_ac']:.2f} A; In ≥ 1.25 × Iac = {ac['mcb_min']:.1f} A"),
        ("RCD-S", "SOLAR AC RCD", f"{ac['rcd']['a']} A {ac['rcd']['poles']}-pole, {ac['rcd']['ma']} mA, "
         f"{ac['rcd']['type']}", f"Rating ≥ MCB {ac['mcb']['a']} A (MS IEC 60364-4-41)"),
        ("ASPD", "AC SURGE PROTECTION", f"Type II AC SPD {ac['spd']['poles']}-pole, Uc {ac['spd']['uc_v']} V, "
         f"In {ac['spd']['in_ka']} kA, Imax {ac['spd']['imax_ka']} kA, c/w {ac['spd']['backup_a']} A backup MCB",
         f"Uc ≥ {ac['spd']['uc_v']} V"),
        ("PCC", "MDB SOLAR WAY", f"Dedicated {mdb['solar_way_a']} A {mdb['solar_way_poles']} MCB in existing "
         f"consumer MDB, labelled \"SOLAR PV FEED\"", "Point of common coupling"),
        ("MDB", "CONSUMER MAIN DB", f"Main switch {mdb['main_switch_a']} A {mdb['main_switch_poles']}; RCCB "
         f"{mdb['main_rcd_a']} A {mdb['main_rcd_ma']} mA; existing domestic circuits", "Existing - verify on site"),
        ("E", "EARTHING", f"{d['earth']['bond_mm2']} mm² G/Y module bonding; {d['earth']['pe_mm2']} mm² PE to MET; "
         f"{R.EARTH_ROD.lower()}", f"R earth < {R.EARTH_RESISTANCE_MAX_OHM} Ω"),
        ("KWH", "TNB METER", f"TNB bi-directional smart meter (kWh), {tnb['meter'].lower()}, import & export "
         f"registers - by TNB", "After Form G & H validation"),
        ("CO", "TNB CUT-OUT", f"{tnb['cutout_a']} A HRC cut-out fuse + neutral link, service cable "
         f"{tnb['service_cable']} - by TNB", "Sealed by TNB"),
    ]
    return rows


def draw_schedule(sh, d, p):
    x0, y0 = 10.0, 191.0
    sh.text(12, y0 + 4.2, "EQUIPMENT SCHEDULE & SIZING BASIS", 2.2, bold=True)
    cols = [("TAG", 12), ("DESCRIPTION", 30), ("SPECIFICATION", 160), ("SIZING BASIS / CHECK", 104)]
    rows = schedule_rows(d, p)
    rh = min(4.4, (286.0 - (y0 + 10.5)) / len(rows))
    yh = y0 + 6
    sh.rect(x0, yh, 306, 4.5, "hdr")
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
        sh.line(x0, y, x0 + 306, y, "th")
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
        sh.text(x + 37, yy, value or "______________________", 1.55, max_w=w - 38)
        yy += 4.1
    sh.text(x + 1.5, y + h - 7, "Signature: ____________________", 1.55)
    sh.text(x + 1.5, y + h - 2.5, "Date:  ___ / ___ / ______", 1.55)
    sh.rect(x + w - 24, y + 21, 22, 13.5, "box")
    sh.text(x + w - 13, y + 28.6, stamp_label, 1.4, "middle")


def draw_side(sh, d, p):
    x, w = 318.0, 90.0
    prot = [(a, b, c) for a, b, c in R.PROTECTION_SETTINGS]
    y = table(sh, x, 12, "TNB MANDATORY INVERTER PROTECTION SETTINGS", ["PARAMETER FUNCTION",
              "TRIP VOLTAGE / FREQUENCY", "CLEARING"], prot, [34, 36, 20], 4.1)
    checks = [(a, b, c, "OK" if ok else "FAIL") for a, b, c, ok in check_rows(d)]
    y = table(sh, x, y + 3, "DESIGN VERIFICATION", ["CHECK", "RESULT", "LIMIT", ""], checks, [32, 22, 24, 12], 3.9)

    notes = [
        f"Installation to {', '.join(R.GOVERNING_STANDARDS[:4])}; symbols to IEC 60617.",
        "Indirect (behind-the-meter) connection: PV feeds the consumer MDB via a dedicated solar way; "
        "TNB meter is bi-directional.",
        "TT earthing. All exposed metalwork bonded; SPD earth leads < 0.5 m; earth electrode R < 10 Ω.",
        "DC and AC isolators lockable in the OFF position and within sight of the inverter.",
        "Warning labels at MDB, ACDB, meter and inverter: \"DUAL SUPPLY - ISOLATE BOTH BEFORE SERVICING\".",
        "Inverter protection settings per TNB table above; to be tested and recorded at commissioning "
        "(MS IEC 62446).",
        "Cable lengths and existing MDB arrangement to be verified on site.",
    ]
    y += 3
    sh.text(x, y + 2, "GENERAL NOTES", 1.9, bold=True)
    y += 4.6
    for i, n in enumerate(notes, 1):
        sh.text(x, y, f"{i}.", 1.5)
        y = sh.para(x + 3, y, n, w - 3, 1.5, 1.25) + 0.5
    people = p["people"]
    yq = 285.0 - 44 - 2 * 38
    draw_legend(sh, x, y + 1.5, w, yq - 2)
    stamp_block(sh, x, yq, w, "SEDA MALAYSIA QUALIFIED PERSON (QP) ENDORSEMENT", [
        ("Qualified Person Name:", people.get("qp_name")),
        ("SEDA GCPV Cert. No.:", people.get("qp_cert_no")),
        ("Registered Svc Provider:", people.get("rpvsp")),
    ], "OFFICIAL QP STAMP")
    stamp_block(sh, x, yq + 38, w, "SURUHANJAYA TENAGA (ST) REGISTERED COMPETENT PERSON", [
        ("Competent Person Name:", people.get("cp_name")),
        ("Category:", people.get("cp_category") or "PW4 / A0 / PEPC"),
        ("ST Competency Cert. No.:", people.get("cp_cert_no")),
        ("ST Contractor Reg. (Form Q):", people.get("contractor_reg_no")),
    ], "OFFICIAL ST STAMP")
    draw_title_block(sh, d, p, x, yq + 76, w, 285.0 - (yq + 76))


def draw_legend(sh, x, y, w, y_max):
    items = [
        ("PV MODULE", lambda cx, cy: pv_module(sh, cx + 1, cy, 7, 3.6)),
        ("SWITCH-DISCONNECTOR", lambda cx, cy: switch(sh, cx, cy, 0, "isolator", 4.5, 0.75)),
        ("CIRCUIT BREAKER (MCB)", lambda cx, cy: switch(sh, cx, cy, 0, "breaker", 4.5, 0.75)),
        ("RCD / RCCB", lambda cx, cy: switch(sh, cx + 1, cy, 0, "rcd", 5.0, 0.75)),
        ("FUSE", lambda cx, cy: fuse(sh, cx, cy, 0, 4.5)),
        ("SURGE PROTECTIVE DEVICE", lambda cx, cy: spd(sh, cx, cy, 0, 4.5)),
        ("EARTH ELECTRODE", lambda cx, cy: earth(sh, cx, cy - 2)),
        ("EARTH CONDUCTOR", lambda cx, cy: sh.line(cx - 4.5, cy, cx + 4.5, cy, "en")),
        ("ENCLOSURE / BOARD", lambda cx, cy: sh.rect(cx - 4.5, cy - 1.8, 9, 3.6, "box")),
        ("OWNERSHIP BOUNDARY", lambda cx, cy: sh.line(cx - 4.5, cy, cx + 4.5, cy, "dm")),
        ("No. OF CONDUCTORS", lambda cx, cy: (sh.line(cx - 4.5, cy, cx + 4.5, cy), ticks(sh, cx, cy, 4))),
        ("PADLOCK = LOCKABLE OFF", lambda cx, cy: padlock(sh, cx, cy - 0.7)),
    ]
    rows = (len(items) + 1) // 2
    rh = min(5.2, (y_max - y - 6) / rows)
    if rh < 3.6:
        return
    sh.text(x, y + 2, "LEGEND", 1.9, bold=True)
    for i, (label, draw) in enumerate(items):
        cx = x + 6 + (i % 2) * (w / 2)
        cy = y + 6.5 + (i // 2) * rh
        draw(cx, cy)
        sh.text(cx + 7, cy + 0.6, label, 1.4, max_w=w / 2 - 14)


def draw_title_block(sh, d, p, x, y, w, h):
    pr = p["project"]
    sh.rect(x, y, w, h, "frb")
    title = pr.get("title", "PROPOSED GRID-CONNECTED SOLAR PV INSTALLATION UNDER SOLAR ATAP SCHEME")
    yy = sh.para(x + 1.5, y + 3.2, title.upper(), w - 3, 1.85, 1.2, bold=True)
    sh.line(x, yy - 0.8, x + w, yy - 0.8, "th")
    rows = [
        ("ACCOUNT HOLDER", pr.get("account_holder", "")),
        ("ADDRESS", pr.get("address", "")),
        ("TNB ACCOUNT NO.", pr.get("tnb_account_no", "")),
        ("SUPPLY TYPE", d["supply_label"]),
        ("PV CAPACITY (DC)", f"{d['array']['p_dc_kwp']:.2f} kWp"),
        ("INVERTER EXPORT (AC)", f"{d['ac']['p_ac_kw']:.2f} kWac"),
    ]
    yy += 1.6
    for label, value in rows:
        sh.text(x + 1.5, yy, label, 1.4, bold=True)
        vrows = wrap(value, w - 31, 1.5)[:2]
        for i, v in enumerate(vrows):
            sh.text(x + 30, yy + i * 1.9, v, 1.5)
        yy += 2.0 + 1.9 * (len(vrows) - 1) + 0.6
    sh.line(x, yy - 1.4, x + w, yy - 1.4, "th")
    cells = [("DRAWING NO.", pr.get("drawing_no", "")), ("REV", pr.get("revision", "")),
             ("SCALE", "NTS"), ("SHEET", "1 OF 1")]
    widths = [40, 14, 16, 20]
    cx = x
    for (label, value), cw in zip(cells, widths):
        sh.text(cx + 1.2, yy + 0.4, label, 1.25, bold=True)
        sh.text(cx + 1.2, yy + 3.0, value, 1.7, bold=True, max_w=cw - 2)
        cx += cw
        sh.line(cx, yy - 1.4, cx, yy + 4.2, "th")
    yy += 4.2
    sh.line(x, yy, x + w, yy, "th")
    cells = [("DRAWN", pr.get("drawn_by", "")), ("CHECKED", pr.get("checked_by", "")),
             ("APPROVED", pr.get("approved_by", "")), ("DATE", pr.get("date", ""))]
    widths = [20, 20, 22, 28]
    cx = x
    for (label, value), cw in zip(cells, widths):
        sh.text(cx + 1.2, yy + 1.9, label, 1.25, bold=True)
        sh.text(cx + 1.2, yy + 4.5, value, 1.6, max_w=cw - 2)
        cx += cw
        if cx < x + w:
            sh.line(cx, yy, cx, y + h, "th")


def render(d, p):
    sh = Sheet()
    sh.rect(10, 10, 400, 277, "frb")
    sh.line(316, 10, 316, 287, "fr")
    sh.line(10, 191, 316, 191, "fr")
    draw_diagram(sh, d, p)
    draw_schedule(sh, d, p)
    draw_side(sh, d, p)
    if d["issues"].errors:
        sh.add(f'<text x="163" y="110" font-size="13" text-anchor="middle" font-weight="bold" fill="{RED}" '
               f'fill-opacity="0.22" transform="rotate(-18 163 110)">DESIGN CHECK FAILED - NOT FOR SUBMISSION</text>')
    return sh.svg()
