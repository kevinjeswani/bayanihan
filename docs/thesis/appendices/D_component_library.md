# Appendix D: Vulnerability Assessment — Archetype-Specific Loss Estimation

**Thesis:** Jeswani, Kevin Kamlesh (2021). *The Seismic Resilience of Critical Spatially-Distributed Building Portfolios.*
**PDF pages:** 317–351 (printed pages 290–324)

**EXTRACTION STATUS:**
- Tables D-3, D-4, D-8, D-9, D-16 were extracted by Ch6 agent (see `docs/thesis/data/` YAMLs).
- Table D-13 (component quantities) is reserved for agent P3 — NOT extracted here.
- This file covers: D.1 background (P-58/REDi), D.2 (D-1, D-2), D.3 (D-5, D-6, D-7), D.4 (D-10, D-11, D-12), D.6 (D-14, D-15), D.7.2 (utility delays), D.8 (vulnerability result figures).

---

## D.1 FEMA P-58 and REDi Background (Printed Pages 290–295; PDF 317–322)

### D.1.1 FEMA P-58 Methodology

The FEMA P-58 (2018a) procedure:
1. **Input EDP Processing:** Generates a joint lognormal PDF from m ground-motion EDPs at n intensities; simulates N structural response demand sets via Monte Carlo (Yang et al., 2006; 2009). Modelling (β_m) and ground-motion (β_gm) dispersions inflate response covariance matrices.
2. **Collapse Fragility:** Each realization samples collapse probability; collapse triggers replacement cost/time and red tag.
3. **Non-Collapse Path:** Simulated demand vector drives component damage state evaluation via component fragilities. Consequence functions calculate repair costs, times, casualties, red tags.
4. **Irrepairability:** Residual drift compared to a lognormal irrepairability fragility (median θ_res,max = 1%, dispersion β_res,max = 0.3). Exceedance → replacement overrides repair.
5. **Performance Groups (PGs):** Components grouped by floor, direction, and EDP type.

Key implementation: SRAMP (Kinetica Risk, 2019).

### D.1.2 REDi Methodology

REDi v1.0 (Almufti & Willford, 2013) is implemented within SRAMP per iteration.

**Repair Classes:**
- **Repair Class 1:** Heavily damaged structural/non-structural components posing life-safety risk
- **Repair Class 2:** Damaged non-structural components without life-safety risk
- **Repair Class 3:** Minimal/minor cosmetic damage

**Recovery Levels:**
- **Full Recovery:** Repair Classes 1 + 2 + 3 complete
- **Functional Recovery:** Repair Classes 1 + 2 complete
- **Re-Occupancy:** Repair Class 3 components repaired (no life-safety threats)

**Total Downtime = max(Utility disruption time, Delays + Repairs)**
- Delays: Engineering mobilization + Financing + Contractor mobilization (lognormal curves)
- Re-Occupancy not dependent on utility disruptions (emergency alternatives assumed)

---

## D.2 Fragilities; Casualty and Red Tag Consequences

### D.2.1 P-58 Background

Damage State types (D.2.1; printed page 295):
- **(i) Sequential:** progressively worse damage states (most structural components)
- **(ii) Mutually Exclusive:** conditional probabilities for different failure modes
- **(iii) Simultaneous:** independent probability of occurrence (e.g., elevator components)

Unsafe placard (red tag) triggers: individual structural component exceeds a specified DS; assigned as (θ, β)_red_tag fraction of performance group.

### Table D-1: Damage State and Casualty Consequence Summary — Structural
*(Printed page 296; PDF page 323)*

| PH Component | EDP | P-58 Unit | DS Hierarchy | DS | Damage State Description |
|-------------|-----|----------|-------------|-----|------------------------|
| Ductile RCMRF; 1-Side/2-Sides & PT RCMRF; 1-Side/2-Sides | PIDR | 1 EA | Seq(DS1,DS2, MutEx(DS3,DS4)); P(DS3)=0.8; P(DS4)=0.2 | 1 | Light beam/joint cracking > 0.6 in; No significant spalling, no rebar fracture/buckling |
| | | | | 2 | Moderate beam/joint cracking > 0.6 in; Cover spalling exposes transverse and joint rebar; No fracture/buckling |
| | | | | 3 | Heavy beam/joint cracking > 0.6 in; Heavy cover spalling exposes long./trans. rebar; Possible core crushing, rebar fracture/buckling |
| | | | | 4 | = DS2 |
| Non-Ductile RCMRF; 1-Side/2-Sides | PIDR | 1 EA | Seq(DS1,DS2,DS3) | 1 | Light column/beam/joint cracking > 0.6 in; No significant spalling, no rebar fracture/buckling |
| | | | | 2 | Moderate column/beam/joint > 0.6 in; Cover spalling exposes transverse and joint rebar; No fracture/buckling |
| | | | | 3 | Heavy column/beam/joint cracking > 0.6 in; Heavy cover spalling exposes long./trans. rebar; Possible core crushing, rebar fracture/buckling |
| Non-RBS Steel MRF; 1-Side/2-Sides | PIDR | 1 EA | Seq(DS1,DS2,DS3) | 1 | Local beam flange and web buckling |
| | | | | 2 | DS1 plus lateral torsional distortion of beam in hinge region |
| | | | | 3 | Low-cycle fatigue fracture in buckled hinge |
| Steel Column Splice | PIDR | 1 EA | Seq(MutEx(DS1,DS2),DS3); P(DS1)=0.95; P(DS2)=0.05 | 1 | Ductile fracture of groove weld flange splice; Damage obscured or not significant |
| | | | | 2 | Ductile fracture of the groove weld flange splice |
| | | | | 3 | DS1 + complete failure of web splice plate; dislocation of two column segments |
| Steel Column Base Plate | PIDR | 1 EA | Seq(MutEx(DS1,DS2),DS3,DS4); P(DS1)=0.95; P(DS2)=0.05 | 1 | Crack at fusion line (column flange-baseplate weld); Damage obscured or not significant |
| | | | | 2 | Crack at fusion line |
| | | | | 3 | Propagation of brittle crack into column and/or base plate |
| | | | | 4 | Complete fracture of column or weld; Dislocation of column relative to base |

*EA = Per piece; Seq=Sequential; MutEx=Mutually Exclusive; P(DSX)=MutEx probability*

---

### Table D-2: Damage State and Casualty Consequence Summary — Non-Structural
*(Printed page 297; PDF page 324)*

| PH Component | EDP | P-58 Unit | DS Hierarchy | DS | Damage State Description |
|-------------|-----|----------|-------------|-----|------------------------|
| CHB Wall; Solid; Unreinforced | PIDR | 125 SF | Seq(DS1,DS2,DS3) | 1 | Light CHB cracking |
| | | | | 2 | Moderate CHB cracking & corner crushing |
| | | | | 3 | Heavy CHB cracking; Possible collapse; Slight Injury over 50 SF approx. |
| CHB Wall; Solid; Reinforced | PIDR | 125 SF | Seq(DS1,DS2) | 1 | Light CHB cracking |
| | | | | 2 | Moderate CHB cracking & corner crushing |
| CHB with Doors/Windows; Unreinforced | PIDR | 125 SF | Seq(DS1,DS2,DS3,DS4) | 1 | Light CHB cracking |
| | | | | 2 | Moderate CHB cracking & corner crushing |
| | | | | 3 | Heavy CHB cracking; Possible collapse; Minor Window/Door Damage; Slight Injury over 50 SF approx. |
| | | | | 4 | Heavy CHB cracking; Possible collapse; Major Window/Door Damage; Slight Injury over 50 SF approx. |
| CHB with Doors/Windows; Reinforced | PIDR | 125 SF | Seq(DS1,DS2,DS3) | 1 | Light CHB cracking |
| | | | | 2 | Moderate CHB cracking & corner crushing |
| | | | | 3 | Moderate CHB cracking & corner crushing; Minor window/door damage |
| Curtain Wall | PIDR | 30 SF | Seq(DS1,DS2,DS3,DS4) | 1 | Light CHB cracking |
| | | | | 2 | Moderate CHB cracking & corner crushing |
| | | | | 3 | Heavy CHB cracking; Possible partial collapse; Some glass cracking |
| | | | | 4 | Heavy CHB cracking; Possible partial collapse; Glass falls from frame; Very slight injury |
| Suspended Ceiling; Non-Seismic | PFA | 250 SF | Seq(DS1,DS2,DS3) | 1 | 5% Ceiling damage |
| | | | | 2 | 30% Ceiling damage |
| | | | | 3 | 100% Ceiling damage; Slight Injury over 250 SF |
| Suspended Ceiling; Braced | PFA | 250 SF | Seq(DS1,DS2,DS3) | 1 | 5% Ceiling damage |
| | | | | 2 | 30% Ceiling damage |
| | | | | 3 | 100% Ceiling damage; Slight Injury over 250 SF |
| Ceiling Fixtures; Non-Seismic | PFA | 1 EA | Seq(DS1) | 1 | Falls, Breaks; Slight injury over 50 SF |
| Ceiling Fixtures; Seismic | PFA | 1 EA | Seq(DS1) | 1 | Falls, Breaks |
| CIP RC Stairs | PIDR | 1 EA | Seq(DS1,DS2,DS3) | 1 | Local concrete cracking, local spalling |
| | | | | 2 | Extensive concrete cracking/crushing |
| | | | | 3 | Loss of live load capacity |
| Desktop Electronics | PFA | 1 EA | Seq(DS1) | 1 | Falls, does not function; Slight injury over 16 SF |
| Wall-Mounted Electronics | PFA | 1 EA | Seq(DS1) | 1 | Falls, does not function; Slight fatality over 16 SF; Moderate injury over 16 SF |
| Elevator | PFA (at GF = PGA) | 1 EA | Simul(DS1,DS2,DS3,DS4); P{DS1,2,3,4}={0.26,0.79,0.68,0.17} | 1 | Anchorage failure of Controller/machine/motor generator/governor; or rope guard failure |
| | | | | 2 | Distortion/damage of rail/counterweight/counterweight bracket/frame |
| | | | | 3 | Cab stabilizers, walls, or doors damaged |
| | | | | 4 | Cab ceiling damaged; Slight injury over 40 SF |
| Sprinkler Drop | PFA | 100 EA | Seq(DS1,DS2) | 1 | Spraying/dripping/leakage at joints, 0.1 Leaks/drop |
| | | | | 2 | Joints break, major leakage; 0.1 Breaks/drop |
| Sprinkler/Other Piping | PFA | 1000 LF | Seq(DS1,DS2) | 1 | Spraying/dripping/leakage at joints, 0.2 Leaks/20 ft |
| | | | | 2 | Joints break, major leakage; 0.2 Breaks/20 ft |
| Electrical Distribution Equipment | PFA | 1 EA | Seq(DS1) | 1 | Damaged; Inoperative |
| Diesel Generator | PFA | 1 EA | MutEx(DS1,DS2,DS3,DS4); P(DS1)=0.7; P(DS1,2,3)=0.1 | 1 | Anchorage failure of Controller/machine/motor generator/governor |
| | | | | 2 | Damaged: drive shaft misalignment |
| | | | | 3 | Damaged: minor electrical (e.g., failed relay) |
| | | | | 4 | Damaged: exhaust line expansion bellows disconnected |

*EA=Per piece; SF=ft²; LF=ft; Seq=Sequential; MutEx=Mutually Exclusive; P(DSx)=MutEx or Simul probability*

---

## D.3 Cost Derivation

### D.3.2 DPWH Unit Construction Costs

### Table D-5: DPWH-Derived Unit Construction Costs
*(Printed page 302; PDF page 329)*

| Item/Task | Cost (PHP) | Cost Unit | Time (MH) | Time Unit | Notes |
|-----------|-----------|----------|----------|----------|-------|
| Concrete – Manual Mixing | 9,062 | PHP/m³ | 22.2 | MH/m³ | — |
| Formworks | 745 | PHP/m² | 3.28 | MH/m² | Includes assembly & stripping |
| Rebar Works | 88 | PHP/kg | 0.11 | MH/kg | — |
| Steel Works | 124 | PHP/kg | 0.13 | MH/kg | Includes fabrication & erection; "heavy steelworks" (PHILCON) |
| Ceiling Installation | 1,331 | PHP/m² | 2.67 | MH/m² | Wood framing estimate (higher cost, conservative) |
| Ceiling Fixture Installation | 1,754 | PHP/set | 3.45 | MH/set | — |
| Painting (RC or CHB) | 456 | PHP/m² | 1.90 | MH/m² | DPWH wall painting |
| Electrical Fittings (p10) | 1,226 | PHP/set | 4.66 | MH/set | Includes outlet, PVC pipe, wires, utility box |
| Electrical Fittings (p90) | 3,156 | PHP/set | 14.2 | MH/set | Additional switch, junction box |
| CHB – New Wall | 1,490 | PHP/m² | 2.26 | MH/m² | Includes laying, tooling, plastering |
| Plastering (RC or CHB) | 180 | PHP/m² | 0.44 | MH/m² | PHILCON CHB Wall plastering |
| Full Wall + Window/Door Set (p10) | 24,913 | PHP/set | 48.7 | MH/set | Includes small (bathroom) window; ~9.3 m² wall panel |
| Full Wall + Window/Door Set (p50) | 36,773 | PHP/set | 84.9 | MH/set | Swing-type steel casement window; ~9.3 m² wall panel |
| Full Wall + Window/Door Set (p90) | 38,089 | PHP/set | 76.6 | MH/set | Medium Jalousie window + panel door; ~9.3 m² wall panel |
| Full Wall + Partial Window/Door Replacement (p10) | 5,845 | PHP/set | 26.2 | MH/set | Full wall replacement, 100% door & 50% window framing, 10% window panes |
| Full Wall + Partial Window/Door Replacement (p50) | 12,958 | PHP/set | 59.7 | MH/set | |
| Full Wall + Partial Window/Door Replacement (p90) | 17,464 | PHP/set | 67.5 | MH/set | |
| Full Wall + Curtain Wall (p10) | 27,921 | PHP/set | 77.4 | MH/set | Fixed steel casement window; ~8.2 m² wall panel |
| Full Wall + Curtain Wall (p50) | 35,040 | PHP/set | 77.4 | MH/set | Awning + fixed steel casement; ~8.2 m² wall panel |
| Full Wall + Curtain Wall (p90) | 78,370 | PHP/set | 79.3 | MH/set | Sliding/fixed aluminum casement; ~8.2 m² wall panel |
| Full Wall + Partial Curtain Wall Replacement (p10) | 30,558 | PHP/set | 128 | MH/set | Replace 25% fixed steel casement; ~8.2 m² wall panel |
| Full Wall + Partial Curtain Wall Replacement (p50) | 34,127 | PHP/set | 128 | MH/set | Replace 50% fixed steel & awning casement |
| Full Wall + Partial Curtain Wall Replacement (p90) | 40,714 | PHP/set | 68.3 | MH/set | Replace 50% sliding/fixed aluminum |
| Switchgear/Panel Board/MCC Installation | 22,813 | PHP/set | 40 | MH/set | Labour for MCC with "power load center switch gear" (PHILCON) |
| Scaffolding | 300 | PHP/set | — | Crew Rate | 14 m supported area; cost from online sales |
| Shoring | 600 | PHP/set | f = 0.1 | | |

*MH=man-/person-hour; costs adjusted for 3/4-person crew with PHILCON (2018) productivity rates*

---

### D.3.3 Repair Task Summary

### Table D-6: Repair Activity Summary — Structural
*(Printed page 303; PDF page 330)*

| PH Component | DS | Damage State Repair Activity | Repair Cost & Time Notes |
|-------------|-----|----------------------------|------------------------|
| Ductile RCMRF; 1-Side/2-Sides & PT RCMRF; 1-Side/2-Sides | 1 | Surface prep; Epoxy injection; Patch with grout | PT has 0.5×C_repair of non-PT; Adjusted for PH beam-column sizes & RC costs |
| | 2 | Surface prep; Remove loose concrete; Clean rebar; Epoxy injection; Formworks; Cast new concrete | |
| | 3 | Surface prep; Remove loose concrete; Clean rebar; Replace damaged rebar; Formworks; Cast new concrete | PT has 0.5×C_repair but 2×time vs. non-PT |
| | 4 | = DS2 | = DS2 |
| Non-Ductile RCMRF; 1-Side/2-Sides | 1 | Surface prep; Epoxy injection; Patch with grout | Adjusted for PH beam-column sizes; Adjusted upwards for cracking of both beams & columns |
| | 2 | Surface prep; Remove loose concrete; Clean rebar; Epoxy injection; Formworks; Cast new concrete | |
| | 3 | Surface prep; Remove loose concrete; Clean rebar; Replace damaged rebar; Formworks; Cast new concrete | |
| Non-RBS Steel MRF; 1-Side/2-Sides | 1 | Surface prep; Heat protection; Heat straightening; Fireproofing | — |
| | 2 | Cut, remove, & replace beam; Weld at column & beam; Cut, remove, replace deck, concrete, rebar; Fireproofing | Original P-58 DS2=DS3; Scaled down DS2 to 0.75×DS3 |
| | 3 | Same as above (full beam replacement) | |
| Steel Column Splice | 1 | Damage not observable or not warranting repair | — |
| | 2 | Surface prep (gouge out); Re-weld | — |
| | 3 | Surface prep (gouge out); Re-weld; Realign columns | — |
| Steel Column Base Plate | 1 | Damage not observable or not warranting repair | — |
| | 2 | Surface prep (gouge out); Re-Weld; Remove & replace grade slab | — |
| | 3 | Remove & replace base plate; Remove & splice in new column portion; Remove & replace grade slab | — |
| | 4 | = DS3, but full column replacement | — |

*Cost of shoring and/or scaffolding for most DS; costs for 1-sided and 2-sided based on estimated quantities.*

---

### Table D-7: Repair Activity Summary — Non-Structural
*(Printed page 304; PDF page 331)*

| PH Component | DS | Damage State Repair Activity | Notes |
|-------------|-----|----------------------------|-------|
| CHB Wall; Solid; Unreinforced | 1 | Paint & plaster | Using P-58-3 "reinforced masonry walls" as skeleton with DG19 repair quantities; No new doweling into frame |
| | 2 | Demolish & rebuild partially damaged CHB; Epoxy injection; Plaster & paint | |
| | 3 | Demolish & rebuild full CHB panel; Epoxy injection; Plaster & paint; Replace electrical outfits | |
| CHB Wall; Solid; Reinforced | 1 | Plaster & paint | Similar to unreinforced but no total collapse |
| | 2 | Demolish & rebuild partially damaged CHB; Epoxy injection; Plaster & paint | |
| CHB with Doors/Windows; Unreinforced | 1 | Plaster & paint | Similar to standard CHB wall with partial window damage at DS3; No new doweling into frame |
| | 2 | Demolish & rebuild partially damaged CHB; Epoxy injection; Plaster & paint | |
| | 3 | Demolish & rebuild full CHB panel; Epoxy injection; Plaster & paint; Remove & replace partially damaged windows/doors | |
| | 4 | = DS3 + Replace full set of doors/windows | Total replacement |
| CHB with Doors/Windows; Reinforced | 1 | Plaster & paint | Similar to unreinforced, but no total collapse & replacement |
| | 2 | Demolish & rebuild partially damaged CHB; Epoxy injection; Plaster & paint | |
| | 3 | Demolish & rebuild partially damaged CHB; Epoxy injection; Plaster & paint; Remove & replace partially damaged windows/doors | |
| Curtain Wall | 1–4 | Same as CHB with Doors/Windows; Includes temporary weather protection | Adjusted for larger/more expensive curtain-wall type windows; Smaller P-58 units |
| Suspended Ceiling; Non-Seismic/Braced | 1 | Replace 5% of ceiling; Electrical modifications | Direct PH costs for ceiling and fixture installation |
| | 2 | Replace 30% of ceiling; Electrical modifications; Replace some lighting fixtures | |
| | 3 | Demolish remaining & replace 100% of ceiling; Reinstall new electrical and fixtures | |
| Ceiling Fixtures; Non-Seismic/Braced | 1 | Replace & install new fixtures; Electrical modifications | — |
| CIP RC Stairs | 1 | Minor repair of finishes; Epoxy Injection | PH costs for casting of new RC |
| | 2 | Shoring; Cut out damaged sections/patch; Replace buckled rebar; Patch/repair adjacent finishes | |
| | 3 | Remove damaged stair set; Shoring; Cast new stair; Install new balustrade; Patch/repair adjacent finishes | |
| Desktop/Wall-Mounted Electronics | 1 | Replace | — |
| Elevator | 1 | Replace/fix controller anchorage, machine anchorage, motor generator, governor anchorage, rope guards | — |
| | 2 | Replace/fix rails, intermediate/counterweight/car bracket, car/counterweight/car guide shoes, tail sheave | |
| | 3 | Replace/fix cab stabilizers/walls/doors | |
| | 4 | Replace/fix cab ceiling | |
| Sprinkler Drop | 1 | Replace 1 sprinkler head per 100; Mechanical/electrical modifications | — |
| | 2 | Repair 1 sprinkler joint per 1000 ft section; Mechanical/electrical modifications | |
| Sprinkler/Other Piping | 1 | Repair pipe & nozzles per 1000 ft section | — |
| | 2 | Repair 20 ft section per 1000 ft section | |
| Electrical Distribution Equipment | 1 | Replace Switchgear/Panel Board/MCC; Mechanical/electrical modifications | — |
| Diesel Generator | 1 | Repair pipe & nozzles | — |
| | 2 | Overhaul - drive shaft misalignment | |
| | 3 | Minor electrical repair (e.g., replace relay) | |
| | 4 | Reconnect exhaust line | |

*Scaffolding included for most elevator DS where necessary.*

---

## D.4 Mitigation Costing

### D.4.1 Unit Mitigation Construction Costs

### Table D-10: Unit Mitigation Construction Costs
*(Printed page 308; PDF page 335)*

| Item/Task | Cost (PHP) | Cost Unit | Time (MH) | Time Unit | Notes |
|-----------|-----------|----------|----------|----------|-------|
| CFRP Application (1-Layer) | 2,072 | PHP/m² | 7.2 | MH/m² | Labour, equipment, & minor materials only; Material costs from Sika PH |
| Manual Excavation | 1,789 | PHP/m³ | 8.0 | MH/m³ | PHILCON/DPWH "structural excavation - rock, manual" |
| Gravel Bedding | 664 | PHP/m³ | 3.0 | MH/m³ | DPWH-based |
| Slab on Grade Demolition | 768 | PHP/m² | 2.9 | MH/m² | RSMeans equipment and labour; Hauling factors for disposal |
| CHB – Demolition | 524 | PHP/m² | 2.0 | MH/m² | RSMeans equipment and labour |
| CHB – Re-toothing | 181 | PHP/m² | 1.1 | MH/m² | RSMeans equipment and labour |
| CHB – New Expansion Joint | 369 | PHP/m | 0.1 | MH/m | Proxy for polyethylene wall joints (Yekrangnia & Seyri, 2019); RSMeans 4×(cross-shaped masonry joints) |
| CHB – Post-Installed Dowels into Frame | 484 | PHP/each | 0.8 | MH/each | RSMeans for chemical anchoring, layout, drilling; converted with r_PH |
| CHB – Welded Wire Mesh | 147 | PHP/m² | 0.07 | MH/m² | RSMeans W6x6 fabric; converted material cost with r_PH |
| CHB – Mortar Overlay | 333 | PHP/m² | 0.4 | MH/m² | PHILCON-based; Labour for plastering; 3× material cost |
| Ceiling – Steel Framing Seismic Bracing | 699 | PHP/m² | 2 | MH/m² | DPWH steel framed ceiling; 0.5(fiber cement board) + 0.5(labour) proxy for steel bracing |
| Ceiling Fixture Anchorage Upgrade/Safety Cables | 583 | PHP/set | 1.2 | MH/set | Proxy from lighting fixture installation — 0.5(labour) + 0.25(material cost) |
| Wall-Mounted Electronics Upgrade | 583 | PHP/set | — | — | Assume = ceiling fixture upgrade |
| Desktop Electronics Anchorage | 292 | PHP/set | — | — | Assume 0.5 × ceiling fixture upgrade |

*RSMeans (Gordian, 2011)*

---

### D.4.2 Archetypal Cost Estimates

### Table D-11: FRP Retrofit Costing for C1-M (Pre/Lo)
*(Printed page 309; PDF page 336)*

**Beams:**
- Beam Length: 455 m
- Beam Surface Area: 173 m²
- Cost: Resin (Sikadur 330): PHP 237,000
- Cost: FRP (SikaWrap 230C): PHP 257,000
- Cost: FRP Labour: PHP 606,000
- Cost: Paint: PHP 70,000

**Joints:**
- Joint Length: 368 m
- Joint Surface Area: 184 m²
- Cost: Resin: PHP 192,000
- Cost: FRP (SikaWrap 230C): PHP 208,000
- Cost: FRP Labour: PHP 572,000
- Cost: Paint: PHP 42,000

**Columns:**
- Column Length: 2,520 m
- Column Surface Area: 368 m²
- CHB Demolition/Reinstallation: 136 m²
- Grade Slab Demolition/Cast New: 72 m²
- Fill Below Slab Excavation/Backfill: 32 m³
- Cost: Resin: PHP 1,313,000
- Cost: FRP (SikaWrap 230C): PHP 1,420,000
- Cost: FRP Labour: PHP 1,824,000
- Cost: CHB Demolition/Reinstallation: PHP 252,000
- Cost: Grade Slab Demolition/Cast New: PHP 370,000
- Cost: Excavation & Backfill: PHP 78,500
- Cost: Paint: PHP 168,000

---

### Table D-12: Archetypal Non-Structural Component Upgrade Cost and Unit Costs
*(Printed page 310; PDF page 337)*

| Item | C1-M (Hi) | C1-M (Mid) | C1-M (Pre/Lo) | C1-L (Mid/Hi) | PTC1-M (Hi) | PTC1-M (Mid) |
|------|----------|-----------|-------------|------------|-----------|-----------|
| **Stories** | 4 | 3 | 3 | 2 | 5 | 5 |
| **Gross Floor Area (m²)** | 1,026 | 916 | 916 | 599 | 2,737 | 1,080 |
| **CHB Upgrade** | | | | | | |
| CHB; Solid (m²) | — | 701 | 701 | 300 | — | 670 |
| CHB; Perforated (m²) | — | 319 | 319 | 328 | — | 403 |
| Welded Wire Mesh (m²) | — | 1,785 | 1,785 | 994 | — | 1,824 |
| Chemical Anchors (ea) | — | 615 | 615 | 342 | — | 628 |
| Saw-Cut/Demolish (m²) | — | 53 | 53 | 32 | — | 55 |
| Re-toothing (m) | — | 527 | 527 | 324 | — | 554 |
| Expansion Joint (m) | — | 527 | 527 | 324 | — | 554 |
| Mortar (2 faces, m²) | — | 1,785 | 1,785 | 994 | — | 1,824 |
| Paint (m²) | — | 1,785 | 1,785 | 994 | — | 1,824 |
| Total Cost (mil. PHP) | — | 2.286 | 2.163 | 1.291 | — | 2.345 |
| Unit Cost (PHP/m²) | — | 2,500 | 2,370 | 2,160 | — | 2,180 |
| **Ceiling Upgrade/Replacement** | | | | | | |
| Ceilings (m²) | 341 | 269 | 269 | 299 | 741 | 432 |
| Replace/Upgrade? | Replace | Replace | Replace | Replace | Upgrade | Replace |
| Total Cost (mil. PHP) | 0.383 | 0.302 | 0.302 | 0.336 | 0.518 | 0.485 |
| Unit Cost (PHP/m²) | 380 | 330 | 330 | 570 | 190 | 450 |
| **Ceiling Fixture Upgrade** | | | | | | |
| Ceiling Fixtures (ea) | 101 | 87 | 87 | 49 | 329 | 157 |
| Total Cost (mil. PHP) | 0.059 | 0.051 | 0.051 | 0.029 | — | 0.092 |
| Unit Cost (PHP/m²) | 60 | 60 | 60 | 50 | — | 90 |
| **Wall-Mounted & Desktop Electronics** | | | | | | |
| Wall Electronics (ea) | — | — | — | — | 24 | 12 |
| Desktop Electronics (ea) | — | — | — | — | 51 | 30 |
| Total Cost (mil. PHP) | — | — | — | — | 0.029 | 0.016 |
| Unit Cost (PHP/m²) | — | — | — | — | 11 | 15 |
| **Structural Retrofit** | | | | | | |
| Unit Cost (PHP/m²) | — | — | 11,000 | — | — | — |
| **TOTAL UNIT COST (PHP/m²)** | **440** | **2,880** | **3,520** | **2,770** | **200** | **2,720** |

*Also applicable to: C4-M (Mid) → same as C1-M (Mid); PTC1-M (Pre/Lo) → same as PTC1-M (Mid).*
*"Ceiling replacement required where wood-framed ceilings expected, else seismic upgrade only."*

---

## D.6 Building Performance Model: Other P-58 Inputs

### Table D-14: Archetypal Unit Replacement Cost
*(Printed page 312; PDF page 339)*

| Archetype | Unit Replacement Cost (PHP/m²) | Source |
|-----------|-------------------------------|--------|
| C1-M, C1-L | 19,790 | QC Inventory Median Cost for "Concrete" buildings (2010+) |
| PTC1-M | 26,250 | QC Inventory Median + 1 Std. Dev. Cost for "Concrete" buildings (2010+) |
| C1-H | 30,530 | QC Inventory Median + 2 Std. Dev. Cost for "Concrete" buildings (2010+) |
| S1-M | 30,530 | QC Inventory Median Cost for "Steel" buildings (2010+) |
| S3-L | 18,030 | GMMA-RAP (Bautista M. L., et al., 2014) |
| CHB-L | 7,815 | GMMA-RAP |
| CWS-L | 10,820 | GMMA-RAP |
| N-L | 1,440 | GMMA-RAP |
| W-L | 6,730 | GMMA-RAP |

*Values inflated to 2020 (WorldData.info, 2020).*

---

### Table D-15: Assumed Replacement Time Delays
*(Printed page 312; PDF page 339)*

| Replacement Cost (PHP) | Engineering Mobilization & Permitting (weeks) | Financing (weeks) | Contractor Mobilization (weeks) | Total Delays (weeks) | Total Delays (days) |
|----------------------|----------------------------------------------|-------------------|--------------------------------|---------------------|---------------------|
| 2,000,000 | 1 | 8 | 1 | 10 | 70 |
| 10,000,000 | 2 | 36 | 4 | 42 | 294 |
| 50,000,000 | 4 | 48 | 4 | 56 | 392 |
| 100,000,000 | 6 | 56 | 4 | 66 | 462 |
| 500,000,000 | 16 | 72 | 8 | 96 | 672 |
| 1,000,000,000 | 20 | 80 | 12 | 112 | 784 |
| 1,500,000,000 | 24 | 96 | 16 | 136 | 952 |

---

## D.7 REDi Definitions

### D.7.2 Utility Delays
*(Printed page 314; PDF page 341)*

Utility delay times adopted from REDi v1.0 (Almufti & Willford, 2013):

- **Electrical Systems:** T_min, T_max = {3, 14} days
- **Natural Gas (not applicable to Metro Manila):**
  - RR ≤ 0.2: {10, 36} days
  - RR > 0.2: {42, 90} days
- **Water Systems:**
  - RR ≤ 0.2: {4, 8} days
  - RR > 0.2: {21, 90} days
- **Repair Rate formula:** RR = 0.034 × PGV^0.98 (repairs per unit length; PGV = peak ground velocity)

*(REDi Repair Class Assignments in Table D-16 are extracted in existing `component_fragilities.yaml`)*

---

## D.8 Vulnerability Results (Figures Only)
*(Printed pages 314–324; PDF pages 341–351)*

These pages contain output figures from SRAMP (Kinetica Risk, 2019) archetype-specific loss estimation — not tabular data.

### D.8.1 Mean Component Loss and Downtime Breakdowns (Figures D-6 to D-10)

| Figure | Content | PDF Page |
|--------|---------|----------|
| D-6 | Mean component loss and downtime: C1-L/C1-M (Mid-Hi) – Soil C | 342 |
| D-7 | Mean component loss and downtime: C1-L/C1-M (Pre/Lo) – Soil C | 343 |
| D-8 | Mean component loss and downtime: PTC1-M (Mid-Hi) and S1-M (Hi) – Soil C | 344 |
| D-9 | Mean component loss and downtime: Secondary archetypes | 345 |
| D-10 | Mean component loss and downtime: Secondary archetypes (continued) | 346 |

### D.8.2 Mean Casualty Breakdowns (Figures D-11, D-12)

| Figure | Content | PDF Page |
|--------|---------|----------|
| D-11 | Mean injury and fatality breakdown: C1M/C1L (Mid-Hi), S1M (Hi) – Soil C | 347 |
| D-12 | Mean injury and fatality breakdowns: PTC1-M (Mid-Hi) | 348 |

### D.8.3 Vulnerability Curves (Figures D-13 to D-15)

| Figure | Content | PDF Page |
|--------|---------|----------|
| D-13 | Vulnerability curves: C1M (Mid-Hi), S1-M (Hi) – Soil C | 349 |
| D-14 | Vulnerability curves: C1-L (Pre-Hi) – Soil C | 350 |
| D-15 | Vulnerability curves: PTC1M (Mid-Hi) – Soil C | 351 |

---

## Key References

- Almufti, I., & Willford, M. (2013): REDi Rating System v1.0
- Bautista M. L., et al. (2014): GMMA-RAP building replacement costs
- DPWH (2017b): Department of Public Works and Highways unit costs
- FEMA P-58 (2018a): Seismic Performance Assessment of Buildings
- Gordian / RSMeans (2011): Unit construction costs
- Kinetica Risk (2019): SRAMP implementation
- PHILCON (2018): Philippine construction cost schedule
- Sika PH: SikaWrap 230C and Sikadur 330 material costs
- WorldData.info (2020): Philippine inflation factors
- Yang et al. (2006; 2009): Monte Carlo demand simulation
- Yekrangnia & Seyri (2019): Polyethylene wall joint proxy
