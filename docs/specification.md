# Engineering Specification & Ruleset: Malaysian Residential Solar PV Single Line Diagram (SLD)

## 1. Scope & Regulatory Framework
This document provides the technical parameters, visual hierarchy, calculation formulas, and statutory annotation standards required to generate an engineering Single Line Diagram (SLD) compliant with residential grid-connected photovoltaic (GCPV) installations under the Malaysian **Solar ATAP** scheme.

### 1.1 Governing Standards
All diagram generation logic must adhere strictly to the following standards:
* **MS IEC 60364-7-712**: Electrical Installations of Buildings – Requirements for Special Installations: Solar Photovoltaic (PV) Power Supply Systems.
* **MS 1837**: Installation of Grid-Connected Photovoltaic (PV) Systems.
* **MS IEC 62446**: Grid-Connected PV Systems – Minimum Requirements for System Documentation, Commissioning Tests, and Inspection.
* **TNB Technical Guidebook**: Technical Guidelines for Interconnection of Distributed Generation to the Distribution System.
* **Electricity Supply Act 1990 (Act 447) & Electricity Regulations 1994**: National electrical safety standards.
* **IEC 60617**: Graphical Symbols for Electrical Diagrams.

---

## 2. Linear Electrical Architecture & Diagram Topology

Residential Solar ATAP systems connect to the grid via an **indirect connection** (behind-the-meter, tied into the consumer distribution board). The drawing topology must flow linearly from **DC Generation (Top/Left)** down to the **Utility Point of Common Coupling (Bottom/Right)**.

```
[PV Array: Strings & Modules]
              │
              ▼
    [DC Combiner Box / SPD]
              │
              ▼
       [DC Isolator]
              │
              ▼
   [Grid-Connected Inverter]
              │
              ▼
       [AC Isolator]
              │
              ▼
[Solar AC Sub-Board: MCB, RCD, SPD]
              │
              ▼
[Point of Common Coupling (PCC): Consumer Main Distribution Board (MDB)]
              │
  ════════════╪════════════ Demarcation Boundary (Ownership Line)
              │
[TNB Bi-directional Revenue Smart Meter]
              │
              ▼
   [TNB Cut-Out Fuse & Neutral]
              │
              ▼
      [TNB Utility Grid]
```

---

## 3. Parametric Calculations & Engineering Formulas

The AI drawing engine must validate and size all displayed protection devices, cables, and current thresholds using the following standard sizing relationships:

### 3.1 DC Side Calculations
* **Array Peak Power ($P_{\text{dc}}$)**:
  $$P_{\text{dc}} = N_{\text{modules}} \times P_{\text{module\_wattage}}$$
* **String Open Circuit Voltage ($V_{\text{oc\_string}}$)**:
  $$V_{\text{oc\_string}} = N_{\text{series}} \times V_{\text{oc\_module}}$$
  *Constraint:* $V_{\text{oc\_string\_max}} < V_{\text{inverter\_max\_dc\_voltage}}$ under lowest historical ambient temperature.
* **String Short Circuit Current ($I_{\text{sc\_string}}$)**:
  $$I_{\text{sc\_total}} = N_{\text{strings\_parallel}} \times I_{\text{sc\_module}}$$
* **DC Fuse / Breaker Sizing ($I_{\text{fuse}}$)**:
  $$I_{\text{fuse}} \ge 1.25 \times I_{\text{sc\_string}}$$
  *(Where multiple parallel strings feed a single input).*
* **DC Cable Sizing & Voltage Drop ($\Delta V_{\text{dc}}$)**:
  $$\Delta V_{\text{dc}} \le 1.0\%$$
  Cable must be cross-linked polyolefin insulated copper rated $\ge 1.0\text{ kV DC}$ (typically $4\text{ mm}^2$ or $6\text{ mm}^2$).

### 3.2 AC Side Calculations
* **Maximum Continuous AC Current ($I_{\text{ac\_max}}$)**:
  * **Single-Phase ($230\text{ V}$)**:
    $$I_{\text{ac\_max}} = \frac{P_{\text{ac\_rated}}}{V_{\text{nom}}} = \frac{P_{\text{ac}}}{230}$$
  * **Three-Phase ($400\text{ V}$)**:
    $$I_{\text{ac\_max}} = \frac{P_{\text{ac\_rated}}}{\sqrt{3} \times V_{\text{line}}} = \frac{P_{\text{ac}}}{\sqrt{3} \times 400}$$
* **Solar Circuit Breaker Sizing ($I_{\text{breaker}}$)**:
  $$I_{\text{breaker}} \ge 1.25 \times I_{\text{ac\_max}}$$
  Standard residential breaker sizes: $16\text{ A}, 20\text{ A}, 32\text{ A}, 40\text{ A}, 63\text{ A}$ (Curve C).
* **AC Voltage Drop ($\Delta V_{\text{ac}}$)**:
  $$\Delta V_{\text{ac}} \le 1.0\%$$
  Total cumulative voltage drop from inverter terminals to Point of Common Coupling must satisfy:
  $$\Delta V_{\text{total}} = \Delta V_{\text{dc}} + \Delta V_{\text{ac}} \le 2.0\%$$

---

## 4. Component Schedule & SLD Annotation Checklist

Every electrical symbol drawn on the SLD must carry specific parametric labels. Generic unlabelled boxes are subject to immediate technical rejection.

| Schematic Node | Graphic Symbol | Required Annotations & Technical Text | Sizing / Code Constraint |
| :--- | :--- | :--- | :--- |
| **PV Array** | Photovoltaic module block with series/parallel interconnections | • Brand & Model<br>• Module Rating (e.g., $550\text{ W}_{\text{p}}$ Monocrystalline)<br>• String configuration (e.g., $1 \times 10\text{ panels}$)<br>• $V_{\text{oc}}$, $I_{\text{sc}}$, $V_{\text{mp}}$, $I_{\text{mp}}$<br>• Total array capacity (e.g., $5.50\text{ kW}_{\text{p}}$) | Domestic cap: Single-phase $\le 5\text{ kW}_{\text{p}}$, Three-phase $\le 15\text{ kW}_{\text{p}}$ (subject to TNB quota rules). |
| **DC Cable** | Continuous line with polarity notation ($+ / -$) | • Spec: XLPO Solar Cable (EN 50618 / PV1-F)<br>• Size: $1 \times 4\text{ mm}^2$ or $1 \times 6\text{ mm}^2$ Cu<br>• Voltage rating: $1.0 / 1.5\text{ kV DC}$<br>• Conduit: Heavy-duty UV-stabilised PVC or GI conduit | Voltage drop $\Delta V_{\text{dc}} \le 1.0\%$. Red $(+)$ and Black $(-)$ identification. |
| **DC Isolator** | Rotary switch symbol with line isolation gap | • Utilization: DC-PV21B / DC-PV22A<br>• Rating: e.g., $1000\text{ V DC}, 25\text{ A}$<br>• Enclosure: IP65 outdoor rated<br>• Label: *"DC ISOLATOR - LOCKABLE"* | Positioned adjacent to or integrated into inverter body; lockable in OFF position. |
| **DC SPD** | Surge arrester symbol diverted to Earth bar | • SPD Type II DC (Class II)<br>• Max voltage: $U_{\text{cpv}} \ge 1.2 \times V_{\text{oc\_string}}$<br>• Nominal discharge current: $I_{\text{n}} \ge 20\text{ kA}$<br>• Standard: MS IEC 61643-12 | Grounded via dedicated low-impedance bond to Main Earth Terminal. |
| **GCPV Inverter** | Solid rectangle with internal AC/DC diagonal split symbol | • Brand & Model<br>• Rated AC Output: $P_{\text{ac}}$ (e.g., $5.0\text{ kW}$)<br>• MPPT count & string allocations<br>• Output: $230\text{ V}$ 1-Ph or $400\text{ V}$ 3-Ph, $50\text{ Hz}$<br>• Power Factor: $> 0.95$ (lagging/leading)<br>• Total Harmonic Distortion ($\text{THD}$): $< 5\%$ | Compliance: MS IEC 62109-1/-2, IEEE 1547. Built-in anti-islanding. |
| **AC Isolator** | Lockable rotary switch symbol | • Poles: 2-Pole (1-Phase) or 4-Pole (3-Phase)<br>• Current rating: $\ge 1.25 \times I_{\text{ac\_max}}$<br>• Utilization: AC-23A / AC-23B<br>• Label: *"SOLAR PV AC ISOLATOR - LOCKABLE"* | Located within sight of inverter and easily accessible by utility operators. |
| **Solar AC Sub-Board** | Enclosed DB outline housing protective gear | • Label: *"SOLAR AC DISTRIBUTION BOARD (ACDB)"*<br>• Ingress rating: IP55 indoor / IP65 outdoor<br>• Complete with warning sign: *"DUAL SUPPLY - ISOLATE BOTH BEFORE SERVICING"* | Dedicated sub-switchboard isolating the generation system before tie-in. |
| **Solar AC Breaker** | Miniature Circuit Breaker (MCB) / MCCB symbol | • Rated trip current: $I_{\text{n}}$ (e.g., $25\text{ A}, 32\text{ A}$)<br>• Tripping characteristic: Type C Curve<br>• Breaking capacity: $I_{\text{cu}} \ge 6\text{ kA}$ or $10\text{ kA}$ | Protects sub-board and trunk line against generation-side fault inrush. |
| **Solar AC RCD** | Residual Current Device symbol | • Type: Type A or Type B (sensitive to residual DC components)<br>• Sensitivity: $30\text{ mA}$ or $100\text{ mA}$<br>• Rating: $\ge$ upstream MCB continuous rating | Enforces personal electric shock and earth fault isolation per MS IEC 60364-4-41. |
| **AC SPD** | AC surge protector symbol to Earth | • Type II AC Surge Arrester<br>• Continuous operating voltage: $U_{\text{c}} \ge 275\text{ V}$ (1-Ph) / $440\text{ V}$ (3-Ph)<br>• Discharge rating: $I_{\text{n}} \ge 20\text{ kA}$ | Protected by upstream $16\text{ A}$ backup fuse or MCB. |
| **Consumer Main DB** | Busbar array with domestic feeder branches | • Main Switch: Double-pole (1-Ph) / 4-pole (3-Ph) isolator<br>• Main RCD: $100\text{ mA}$ ($300\text{ mA}$ for fire)<br>• Solar Interconnection Way: Dedicated spare breaker labelled *"SOLAR PV FEED"*<br>• Domestic circuits: Lighting, Socket Outlets, Air Conditioner | Point of Common Coupling (PCC) where PV feed synchronises with consumer load bus. |
| **TNB Revenue Meter** | Bi-directional energy meter symbol with import/export indicators | • Label: *"TNB BI-DIRECTIONAL SMART METER (KWH)"*<br>• Displays: Forward (Import) & Reverse (Export) active registers<br>• Phase configuration: 1-Phase 2-Wire or 3-Phase 4-Wire | Demarcation milestone installed by TNB after Form G & Form H validation. |
| **TNB Cut-Out & Link** | Enclosed cut-out fuse symbol + neutral disconnect link | • HRC Fuse: $60\text{ A}$ or $100\text{ A}$<br>• Neutral copper link block<br>• Service cable: $16\text{ mm}^2$ / $25\text{ mm}^2$ concentric or PVC/SWA/PVC copper | Physical intake termination owned and sealed by Tenaga Nasional Berhad. |

---

## 5. TNB Protection Relay Trip Settings Table

The SLD canvas **must** include a dedicated text block detailing the inverter's internal loss-of-mains and voltage/frequency trip thresholds:

```
┌────────────────────────────────────────────────────────────────────────┐
│               TNB MANDATORY INVERTER PROTECTION SETTINGS               │
├──────────────────────────┬─────────────────────────────┬───────────────┤
│ Parameter Function       │ Trip Voltage / Frequency    │ Trip Clearing │
├──────────────────────────┼─────────────────────────────┼───────────────┤
│ Under-Voltage (UV) Level │ V < 196 V (0.85 Un)         │ t <= 2.0 s    │
│ Over-Voltage 1 (OV1)     │ V > 253 V (1.10 Un)         │ t <= 2.0 s    │
│ Over-Voltage 2 (OV2)     │ V > 264 V (1.15 Un)         │ t <= 0.1 s    │
│ Under-Frequency (UF)     │ f < 47.5 Hz                 │ t <= 0.5 s    │
│ Over-Frequency (OF)      │ f > 52.0 Hz                 │ t <= 0.5 s    │
│ Loss of Mains (Islanding)│ Active & Passive Drift      │ t <= 2.0 s    │
│ Reconnection Delay Time  │ Continuous normal stability │ 300 s delay   │
└──────────────────────────┴─────────────────────────────┴───────────────┘
```

---

## 6. Grounding and Bonding Architecture

The diagram must show a continuous, unbroken protective earthing schematic:
1. **Module Frame Equipotential Bonding**:
   * Minimum conductor: $6\text{ mm}^2$ green/yellow PVC copper or bare copper conductor.
   * Connects all anodized aluminum mounting frames and solar module chassis via stainless steel star washers or earthing lugs.
2. **Inverter & ACDB Earthing**:
   * Minimum conductor: $6\text{ mm}^2$ / $10\text{ mm}^2$ copper earth conductor routed to the Main Earth Terminal (MET).
3. **Surge Protection Bonding**:
   * Direct, shortest possible path ($< 0.5\text{ m}$) from SPDs to the Earth Bar.
4. **Earth Electrode**:
   * Copper-bonded steel core earth rod ($16\text{ mm}$ diameter $\times 2.4\text{ m}$ length) driven into soil.
   * Earth Resistance constraint:
     $$R_{\text{earth}} < 10\ \Omega$$

---

## 7. Demarcation & Boundary Visuals

To avoid confusion over equipment ownership and maintenance obligations, draw a bold **Chain-Dashed Line (`- · · - · · -`)** dividing the diagram:

* **TNB Ownership Zone (Upstream of Meter)**:
  * TNB Low Voltage Overhead / Underground Service Line.
  * TNB Cut-Out Fuse, Neutral Link, and Tamper-Proof Service Box.
  * TNB Smart Bi-directional Meter.
* **Consumer Ownership Zone (Downstream of Meter)**:
  * Internal intake sub-main wiring.
  * Consumer Main DB (MDB) & Solar Breaker Way.
  * Solar ACDB, Solar AC Isolator, Inverter.
  * DC cabling, DC Isolators, PV Strings, and Earthing Rods.

---

## 8. Statutory Stamp Boxes and Metadata Block

The bottom-right quadrant of the drawing sheet must feature two mandatory certification blocks alongside the project information table:

### 8.1 SEDA Qualified Person (QP) Block
```
┌────────────────────────────────────────────────────────┐
│     SEDA MALAYSIA QUALIFIED PERSON (QP) ENDORSEMENT    │
├────────────────────────────────────────────────────────┤
│ Qualified Person Name: [Engineer / QP Name]           │
│ SEDA GCPV Certificate No.: GCPV-[Year]-[Number]        │
│ Registered Service Provider (RPVSP): [Company Name]    │
│                                                        │
│ Signature: ______________________                      │
│ Date:      [DD / MM / YYYY]      Official QP Stamp     │
└────────────────────────────────────────────────────────┘
```

### 8.2 Suruhanjaya Tenaga (ST) Competent Person Block
```
┌────────────────────────────────────────────────────────┐
│    SURUHANJAYA TENAGA (ST) REGISTERED COMPETENT PERSON │
├────────────────────────────────────────────────────────┤
│ Competent Person Name: [CP Name]                       │
│ Category: Wireman PW4 / Chargeman A0 / PEPC            │
│ ST Competency Cert. No.: ST-[Number]                   │
│ ST Electrical Contractor Reg. No.: Form Q - [Number]   │
│                                                        │
│ Signature: ______________________                      │
│ Date:      [DD / MM / YYYY]      Official ST Stamp     │
└────────────────────────────────────────────────────────┘
```

### 8.3 Title Block Data Fields
* **Project Title**: Proposed Grid-Connected Solar PV Installation under Solar ATAP Scheme
* **Account Holder**: Must match the exact full name on the TNB electricity bill
* **Installation Address**: Exact physical street address of premises
* **TNB Account No.**: 12-Digit billing account number
* **Supply Type**: Single-Phase $230\text{ V}, 50\text{ Hz}$ OR Three-Phase $400\text{ V}, 50\text{ Hz}$
* **Installed PV Capacity**: e.g., $8.80\text{ kW}_{\text{p}}$ (DC)
* **Inverter Export Rating**: e.g., $7.00\text{ kW}_{\text{ac}}$ (AC)
* **Drawing Index**: e.g., `ATAP-SLD-RES-001`, Rev 01
* **Drawn By / Checked By / Approved By**: Engineering initials with revision dates

---

## 9. AI Drawing Generator Prompt Schema

When feeding this ruleset into an AI CAD or SVG generator, format the system prompt using the following structured payload:

```json
{
  "system_type": "GCPV_Residential_ATAP",
  "supply_configuration": "3-Phase_4-Wire_400V",
  "parameters": {
    "pv_array": {
      "module_model": "Trina Solar Vertex S+ 440W",
      "module_wattage_wp": 440,
      "strings_count": 2,
      "modules_per_string": 10,
      "total_kwp": 8.8,
      "voc_string": 522.0,
      "isc_string": 10.74
    },
    "inverter": {
      "brand_model": "Huawei SUN2000-8KTL-M1",
      "rated_output_kw": 8.0,
      "mppt_channels": 2,
      "ac_voltage": 400,
      "ac_max_current": 13.5
    },
    "dc_protection": {
      "cable_spec": "1x4mm2 Solar Cable PV1-F 1.5kV",
      "isolator_rating": "1000V DC 20A 4-Pole",
      "spd_type": "Type II DC 1000V In=20kA"
    },
    "ac_protection": {
      "sub_board_mcb": "20A 3-Pole 10kA Curve-C",
      "sub_board_rcd": "40A 4-Pole 100mA Type-A",
      "ac_isolator": "25A 4-Pole AC-23A Lockable",
      "ac_spd": "Type II 4-Pole 440V In=20kA"
    },
    "pcc": {
      "connection_type": "Spare 20A 3-Pole MCB in Existing Consumer MDB",
      "tnb_intake_fuse": "60A HRC Cut-Out Fuse",
      "tnb_meter": "Bi-directional 3-Phase Smart Meter"
    }
  }
}
```