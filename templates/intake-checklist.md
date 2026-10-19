# SLD intake checklist

Use this to collect a job, whether you're a person filling it in or an agent asking the
user. Ask for everything missing **in one message**. Items marked * are needed to draw.
Everything else can be left blank and filled in for a later revision.

## A. System *
| Item | Example | Notes |
|---|---|---|
| Supply phase * | 3 | 1 = 230 V single-phase, 3 = 400 V three-phase |
| PV module model * | Jinko JKM650N-66QL6-BDV | Exact model code if possible; a datasheet PDF is best |
| Number of modules * | 17 | |
| Inverter model * | SAJ R6-10K-T2 | Exact size; a datasheet PDF is best |
| String layout | 9 on MPPT 1, 8 on MPPT 2 | If not given, proposed automatically |

## B. Site
| Item | Example | Default if unknown |
|---|---|---|
| DC cable run, array → inverter (one-way) | 25 m | 20 m |
| AC cable run, inverter → MDB | 12 m | 15 m |
| Lowest / highest cell temperature | 15 / 70 °C | 15 / 70 °C (lowlands); use lower for highlands |

## C. Existing consumer MDB
| Item | Default |
|---|---|
| Main switch rating | 63 A |
| Main RCCB rating / sensitivity | 63 A / 100 mA |
| Existing circuits (name + rating) | Lighting 10 A, Socket outlets 20 A, Air-conditioner 20 A |
| TNB cut-out fuse | 60 A |

## D. Title block (needed for submission)
| Item | Notes |
|---|---|
| Account holder | **Exactly** as printed on the TNB bill |
| Installation address | Full street address |
| TNB account number | 12 digits |
| Drawing number and revision | e.g. ATAP-SLD-RES-002, Rev 01 |
| Drawn / checked / approved by | Initials |

## E. Endorsements (needed for submission)
| SEDA Qualified Person | ST Competent Person |
|---|---|
| Name | Name |
| SEDA GCPV certificate no. | Category (PW4 / A0 / PEPC) |
| Registered PV service provider (RPVSP) | ST competency certificate no. |
| | Electrical contractor reg. (Form Q) no. |

## Not needed (the engine sizes these)
DC/AC breakers, RCD, isolators, SPDs, string fuses, cable sizes, earthing conductors,
voltage drop.

---
### Copy-paste request to send a customer or salesperson
```
For the solar SLD please send:
1. Single or three phase?
2. Panel model + quantity, inverter model (datasheets if you have them)
3. Roof-to-inverter and inverter-to-DB cable distance (approx. metres)
4. Photo of the TNB bill (name, address, account no.)
5. Photo of the existing DB (main switch / RCCB ratings)
```
