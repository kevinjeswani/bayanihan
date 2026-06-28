# Appendix C: Development of Building Fragility Functions

**Thesis:** Jeswani, Kevin Kamlesh (2021). *The Seismic Resilience of Critical Spatially-Distributed Building Portfolios.*
**PDF pages:** 273–316 (printed pages 246–289)
**Note (LOW value for v0.1):** This appendix documents the NRHA structural modelling details and archetype re-design procedures. It does NOT need to be re-implemented for v0.1 (no NRHA rebuild). A section summary and table inventory are provided below. Key structural parameters from the archetype comparison tables (C-12 to C-15) are noted but not extracted in full — these are modelling details, not loss estimation inputs.

---

## Contents Summary

### C.1 Review of Structural Design Practice in the Philippines — Pages 246–249 (PDF 273–276)

Documents the National Structural Code of the Philippines (NSCP) edition history and seismic design evolution. Key code vintages define the archetype "Pre/Lo", "Mid", and "Hi" code design levels.

### Table C-1: Summary of Major Changes to NSCP Editions
*Source: Lopez (2018–2020) and ASEP (1972; 1982; 1986; 1992; 2001; 2010; 2016)*

| NSCP Edition | Release Year | Code Basis | Events Leading to Change | Key Changes |
|-------------|-------------|-----------|------------------------|-------------|
| 1st | 1972/1977 | UBC 1970 | 1968 Mw 7.8 Casiguran EQ | Minor seismic ductile detailing provisions |
| 2nd | 1981/1982 | UBC 1979 | — | Structural updates |
| 3rd | 1986 | UBC 1985 | — | Similar to NBCP 1981 |
| 4th | 1992 (1st print), 1996 (2nd) | UBC 1988 / SEAOC Blue Book | — | Near-fault factor; base shear up to 35% lower than NSCP 1982 with ductile detailing |
| 5th | 2001 (2nd print) | UBC 1997 | — | Further updates |

**Note:** NSCP 1992 base shears can be up to 35% lower than NSCP 1982 but include ductile seismic detailing. This suggests NSCP 1992 (Low-Code) may be separated into a Mid-Code vintage.

### Table C-2: NSCP Code Comparison Summary
*(Printed page 248; PDF 275)* — Full comparison matrix of NSCP editions vs. UBC basis.

---

### C.2 Re-Design of Mid-Rise RCMRFs — Pages 249–261 (PDF 276–288)

Presents the structural re-design procedure for the two primary RCMRF archetypes:
- **C1-M (Pre/Lo):** Designed to NSCP 1972/1982 (ASEP, 1972; 1982)
- **C1-M (Mid):** Designed to NSCP 1992 (ASEP, 1992)

**Building geometry (both archetypes):**
- 3 bays transverse (1.75 m hallway + two 3.75 m classroom bays)
- 7 bays longitudinal (4 m staircase + four 6 m classroom + two 2.5 m restroom bays)
- Typical classroom: 7.5 × 6 m (variants: 8–9 m × 6–7 m, two transverse bays, four extra longitudinal bays)
- Height hn = 10.75 m (3-storey)

#### C.2.1 Detailed Re-Design Steps (Tables C-3 to C-7)

**Table C-3: General Loading Summary** *(printed page 251)*

| Load Type | Value | Reference |
|-----------|-------|-----------|
| Roof (live) | 1.0 kPa | ASEP (1972–2001) |
| Classrooms / Teacher's Offices | 2.0 kPa | ASEP (1972–2001) |
| Corridors & Stairs (Above Ground) | 3.8 kPa | DPWH (2017b) |

**Table C-4: Static Lateral Force Procedure Summary** *(printed page 252)*

| Parameter | C1-M (Pre/Lo) | C1-M (Mid) |
|-----------|--------------|-----------|
| Code | NSCP 1972/1982 | NSCP 1992 |
| Seismic Weight | W = 8,132 kN | W = 7,920 kN |
| Z Factor | Z = 1.4 (Poor Soil) | Z = 0.4 (Seismic Zone 4) |
| Importance | I = 1.0 | I = 1.0 |
| Ductility | K = 0.67 (Special MRSF) | R = 10 (RC-MRSF) |
| Height | hn = 10.75 m | hn = 10.75 m |
| Period | T = 0.1N = 0.3 s | T = Ct(hn)^¾ = 0.445 s |
| Site Factor | S = 1.5 (worst case, ~Soil D per DPWH 2017b) | same |

**Tables C-5, C-6, C-7:** Structural design summaries for beams, columns (axial-flexural), and columns (shear, joint shear, splices).

Key material properties:
- Concrete: f'c = 20.7 MPa (both archetypes)
- Rebar (C1-M Pre/Lo): fy,long = fy,trans = 226 MPa (longitudinal & transverse)
- Rebar (C1-M Mid): fy,long = fy,trans = 276 MPa

Typical beam sizes: 300×500 mm to 300×600 mm deep (both).

#### C.2.2 Structural Drawings
Pages C-7 to C-11 (PDF 284–288): Revit (AutoDesk, 2019) structural drawings for C1-M (Pre/Lo) and C1-M (Mid). Not extracted for v0.1 (vision-heavy geometry; not required to rebuild NRHA).

---

### C.3 Simulated FRP Retrofit of C1-M (Pre/Lo) — Pages 262–265 (PDF 289–292)

FRP (Fibre-Reinforced Polymer) retrofit design for the C1-M (Pre/Lo) archetype:
- **Beams:** 3-sided (U-wraps) where no CHB infill below; 2-sided elsewhere. Up to 5 FRP layers for heavily shear-deficient sections (2nd and 3rd storey); no wrapping for roof beams.
- **Columns:** Fully wrapped along clear length (2–3 FRP layers); local demolition of slab-on-grade assumed for access below slab.

#### C.3.1 Detailed Steps
Tables C-8 (beam shear) and C-9 (column shear): FRP design methodology per ACI 440-17, ASCE 41-17. Equations use probable moment capacity, shear demand from hinging mechanism.

#### C.3.2 Results
- Table C-10: Column shear retrofitting results
- Table C-11: Beam shear retrofitting results

*(Quantities from these tables used in Appendix D Table D-11 FRP costing — see D_component_library.md)*

---

### C.4 Structural Comparison of Primary Archetypes — Pages 266–274 (PDF 293–301)

Tabulated structural definitions for all primary archetypes. **v0.1 note:** These are NRHA modelling details. Not extracted to YAML — consult Tables C-12 to C-15 for specific parameters if needed.

| Table | Archetypes | PDF Pages |
|-------|-----------|----------|
| C-12 | Low-Rise RCMRFs: C1-L (Pre/Lo) and C1-L (Mid/Hi) | 294 |
| C-13 | Mid-Rise RCMRFs: C1-M (Pre/Lo), C1-M (Mid), C1-M (Hi) | 295 |
| C-14 | Mid-Rise PTMRFs: PTC1-M (Mid) and PTC1-M (Hi) | 298 |
| C-15 | High-Rise RCMRF (C1-H, Hi) and Mid-Rise SMRF S1-M (Hi) | 301 |

---

### C.5 Non-Linear Modelling — Pages 275–288 (PDF 302–315)

Documents the OpenSees NRHA model parameters for each archetype. Tables summarize:

| Table | Content | PDF Page |
|-------|---------|----------|
| C-16 | Expected material properties for modelled archetypes | 302 |
| C-17 | Ductile beam-column modelling summary | 303 |
| C-18 | Ductile beam-column modelling (continued) | 304 |
| C-19 | Shear hinge backbone definition summary | 304 |
| C-20 | Shear hinge backbone definition (continued) | 305 |
| C-21 | FRP-confined beam-column modelling summary | 306 |
| C-22 | CHB infill compressive strut (in-plane) definition | 307 |
| C-23 | CHB infill compressive strut (in-plane) continued | 308 |
| C-24 | CHB infill out-of-plane actions calculations | 309 |

**C.5.6 EDPs from NRHA:** Engineering Demand Parameter (EDP) output processing (pages 282–288). EDPs extracted: Peak Inter-storey Drift Ratio (PIDR), Peak Floor Acceleration (PFA).

---

### C.6 Simplified Models — Pages 288–289 (PDF 315–316)

Simplified model development summary (for archetypes that are approximated rather than fully modelled in OpenSees).

| Table | Content | PDF Page |
|-------|---------|----------|
| C-25 | Simplified model development summary | 315 |
| C-26 | Simplified model development (continued) | 316 |

---

## Key References

- ASEP (1972; 1982; 1986; 1992; 2001; 2010; 2016): NSCP editions
- AutoDesk (2019): Revit for structural drawings
- ACI 440-17: FRP design standard
- ASCE 41-17: Seismic evaluation and retrofit
- DPWH (2017b): Department of Public Works and Highways structural drawings
- Lopez (2018–2020): Personal communication on NSCP code history
- OpenSees: Non-linear response history analysis platform
