# Chapter 5: Development of Building Fragility Functions

**Source:** Jeswani, K. K. (2021). *The Seismic Resilience of Critical Spatially-Distributed Building Portfolios* [MASc thesis]. University of Toronto.
**Printed pages:** 65–109 (PDF pages 92–136)

---

## 5.0 Overview

Chapter 5 develops structural fragilities for the building archetypes defined in Chapter 4 through two main paths: (1) detailed non-linear response history analysis (NRHA) for primary reinforced concrete moment frame (RCMRF) archetypes; and (2) simplified FEMA P-58 models for remaining primary and secondary archetypes. The ASCE-41 (2017) Tier 3 methodology governs non-linear modelling, with NIST (2017) GCR17-917-46 providing detailed guidance. Philippine NSCP editions are based on American codes (UBC/ACI318/ASCE-7), making the North American ASCE-41 approach appropriate.

The overall process:
1. Review Philippine National Structural Code (NSCP) editions and common failure mechanisms.
2. Use collected structural drawings for modern RCMRFs; conduct simulated re-designs for Pre/Low- and Mid-Code archetypes.
3. Develop non-linear models in SAP2000 (linear elastic) → PERFORM-3D (non-linear dynamic).
4. Run non-linear static pushover (NSP) and non-linear response history analyses (NRHA).
5. Derive collapse fragilities via multiple stripes analysis (MSA) with log-normal maximum likelihood estimation (MLE).
6. Use simplified FEMA P-58 models with HAZUS and UPD-ICE (Pacheco et al., 2014) fragilities for remaining archetypes.

---

## 5.1 Index Buildings for Archetype-Specific Loss Estimation

### 5.1.1 Representation Overview

Table 5-1 (printed p. 67) summarizes how each archetype is represented:

| Group | Archetype ID | System | Drawings/Re-Design? | Merged With | EDP Proxy? | EDP Method |
|-------|-------------|--------|---------------------|-------------|------------|------------|
| Primary – Modelled | C1-L (Mid/Hi) | RCMRF | Drawings | — | — | NRHA |
| Primary – Modelled | C1-M (Hi) | RCMRF | Drawings | — | — | NRHA |
| Primary – Modelled | C1-M (Mid) | RCMRF | Re-Design | — | — | NRHA |
| Primary – Modelled | C1-M (Pre/Lo) | RCMRF | Re-Design | — | — | NRHA |
| Primary – Modelled | C1-M (Pre/Lo) FRP | Retrofit Design | Retrofit Design | — | — | NRHA |
| Primary – EDP Proxy | PTC1-M (Mid) | RCMRF w/ PT-beams | Re-Design | — | C1-M (Mid) | NRHA |
| Primary – EDP Proxy | PTC1-M (Hi) | RCMRF w/ PT-beams | Drawings | — | C1-M (Hi) | NRHA |
| Primary – Simplified | C1-L (Pre/Lo) | RCMRF | Re-Design | — | — | Simplified |
| Primary – Simplified | C1-H (Hi) | RCMRF w/ basement | Drawings | — | — | Simplified |
| Primary – Simplified | S1-M (Hi) | SMRF | Drawings | — | — | Simplified |
| Secondary – Simplified | CWS-L | RCMRF w/ wood frame | — | — | — | Simplified |
| Secondary – Simplified | S3-L | Light steel frame & bracing | — | — | — | Simplified |
| Secondary – Simplified | CHB-L | Reinforced/unreinforced CHB | — | — | — | Simplified |
| Secondary – Simplified | W-L | Wood frame and walls | — | — | — | Simplified |
| Secondary – Simplified | N-L | Wood frame w/ CHB/G.I. | — | — | — | Simplified |
| Merged | PC-L | Precast RCMRF or RCSWs | — | C1-L (Pre/Lo) | — | — |
| Merged | PTC1-M (Pre/Lo) | RCMRF w/ PTG | — | C1-M (Pre/Lo) | — | — |
| Merged | PTC4-M (Lo) | RCMRF w/ PTG & RCSW | — | PTC1-M (Mid) | — | — |
| Merged | C4-L (Lo/Mid) | RCMRF & RCSWs | — | C1-L (Mid/Hi) | — | — |
| Merged | C4-M (Mid) | RCMRF & RCSWs | — | C1-M (Hi) | — | — |

**Merging rationale:**
- PTC1-M (Pre/Lo) merged into C1-M (Pre/Lo): no significant differences in non-structural contents, non-ductile mechanisms, or expected global performance.
- C4-L (Lo/Mid) and C4-M (Mid): dual-system archetypes expected to be slightly more resilient than RCMRF-only counterparts; limited numbers did not warrant additional analyses.
- PTC4-M (Lo) merged with PTC1-M (Mid) for same reason.
- PC-L merged with C1-L (Pre/Lo): precast RCMRF or RCSW with similar pre-code performance.

**EDP-proxy rationale (PTC1-M):** Post-tensioned MRF archetypes in Makati were assigned EDPs of their standard RCMRF counterparts (PTC1-M (Hi) → C1-M (Hi) EDPs; PTC1-M (Mid) → C1-M (Mid) EDPs). Different structural and non-structural components were assigned to reflect Makati building typologies and PT-specific repair costs.

### 5.1.2 Re-Design of Low- and Mid-Code Buildings for Non-Linear Modelling

The C1-M (Pre/Lo) and C1-M (Mid) archetypes required re-design of a typical 3-Storey 12-Classroom RCMRF in Quezon City:
- **C1-M (Pre/Lo):** followed NSCP 1972/1982 provisions (Low-Code). Relaxed stirrup spacing causes shear deficiency in beams; relaxed spacing at column mid-heights causes shear failure at those locations. End-moment capacities are 20–60% greater than C1-M (Mid) due to increased base shear demands.
- **C1-M (Mid):** followed NSCP 1992 provisions.

Rough member sizes and plan/section dimensions taken from RVS observations. Design practice guided by DPWH Low-Code C4-L, C4-M, and C1-L structural drawings (DPWH, 2018) with information from local practitioners.

Detailed re-design steps and resulting drawings are in Appendix C.2.

### 5.1.3 Description of Simulated Structural Retrofit for C1-M (Pre/Lo)

A fibre-reinforced polymer (FRP) retrofit scheme was developed for the non-ductile C1-M (Pre/Lo) archetype to demonstrate retrofit benefits at portfolio level:

- **Product:** SikaWrap-230C (Sika, 2019) — 0.13mm-thick woven uni-directional carbon fibre fabric, 3200 GPa characteristic laminate tensile strength.
- **Application:** Shear strengthening of beams and columns. ACI-440 (2017) guidelines used to bridge gap between beam-end shear demand and capacity. Column-end FRP hinge confinement also provided.
- **CHB infill isolation:** Saw-cutting wall ends and inserting polypropylene-type insulating material to isolate CHB infill walls from participating in the SFRS.
- **OOP wall prevention:** Welded-wire-mesh applied to both sides of wall with grout surface finish.
- **Assumption:** Wide-spread FRP wrapping without extensive building-specific assessments — simulates a rapid, deployable retrofit programme.

Detailed FRP design calculations and fabric quantities are in Appendix C.3.

### 5.1.4 Summary of NRHA Archetypes

**Table 5-2:** Summary of NRHA index buildings (printed p. 70–71):

| Archetype ID | Stories | Layout | Typical Seismic System Features | Failure Modes | Modelling |
|-------------|---------|--------|--------------------------------|---------------|-----------|
| C1-L (Mid/Hi) | 2 | 6-Classroom; Plan: 31.5m (7 bays @ 4.5m) × 9.5m (2 bays @ 2.5m & 7m); Height: 6.7m | 200×400–200×500mm Beams; 350×350mm Columns | Side-sway collapse; Weak-column-strong-beam; No shear failure | Lumped plasticity beam-columns – only flexural or axial-flexural behaviour; CHB infill struts |
| C1-M (Hi) | 4 | ~30-Room; Plan: 27m (6 bays @ 4.5m) × 9.5m (2 bays @ 2.5m & 7m); Height: 13.13m | 300×400–400×550mm, 250×450mm Beams; 400×400–575×575mm Columns | Ductile; Side-sway collapse; Strong-column-weak-beam | Same modelling approach; CHB infill struts |
| C1-M (Mid) | 3 | Plan: 33m (4 bays @ 6m, 2 bays @ 2.5m, 1 bay @ 4m) × 9.25m (1 bay @ 1.75m & 2 bays @ 3.75m); Height: 10.4m | 250×400–300×600mm Beams; 350×350–400×400mm Columns | Side-sway collapse; Weak-column-strong-beam | Elastic shear; lumped plasticity; CHB infill struts |
| C1-M (Pre/Lo) | 3 | Same plan as C1-M (Mid); Height: 10.4m | 200×400–300×600mm Beams; 350×350–450×450mm Columns | Column and beam shear failure due to improper detailing; Weak-column-strong-beam | Similar to C1-M (Mid) but with inelastic shear hinges |
| C1-M (Pre/Lo) FRP | 3 | Same plan | Same as C1-M (Pre/Lo) with FRP wrapped beam-columns in 1st & 2nd stories | Same as C1-M (Hi) — shear failure prevented | Same as C1-M (Hi) — shear hinges removed |

*Failure mode sources: Bautista, et al. (2012); Lopez (2018–2020)*

**Note on C1-M (Hi) stirrup deficiency:** Early 2010s DepEd standard drawings specified stirrup spacing of 150mm in 2.5m hallway bay transverse MRF beams, resulting in shear deficiency. Buildings built to these early-2010s DepEd standards are recommended for rebar scanning. This mechanism was not considered in modelling C1-M (Hi) since it should not be characteristic of High-Code buildings.

### 5.1.5 Summary of Non-NRHA Index Buildings

**Table 5-3:** Summary of non-NRHA index buildings (printed p. 72–73):

**Primary – EDP Proxy:**

| Archetype ID | Stories (Proxy) | Layout | Features | Possible Failure Modes |
|-------------|----------------|--------|----------|----------------------|
| PTC1-M (Mid) | 5 (3) | ~15-Room; Plan: 32m (4 bays @ 8m) × 9m (2 bays @ 3m & 6m); Height: 16.45m | 300×400–300×800mm Beams; 500×500–850×850mm Columns | Side-sway collapse; Possible PT anchorage failure; Possibly less residual drifts |
| PTC1-M (Hi) | 5 (4) | ~30-Room; Plan: 64m (8 bays @ ~8m) × 8.5m (2 bays @ 2.5m & 6m); Height: 18.6m | 250×400–300×600mm Beams; 400×400–750×750mm Columns | Same as C1-M (Hi); Less cracking; Side-sway collapse |

**Primary – Simplified:**

| Archetype ID | Stories | Layout | Features | Possible Failure Modes |
|-------------|---------|--------|----------|----------------------|
| C1-L (Pre/Lo) | 2 | ~6-Classroom; Plan: 27m (7 bays @ 3.5–4m) × 7m (1 bay); Height: 7m | 250×300–250×600mm Beams; 200×300–300×300mm Columns | Non-Ductile; Similar to C1-M (Pre/Lo); Using general computational Philippine fragility (UPD-ICE) |
| C1-H (Hi) | 10 (+2) | Plan: 70m (14 bays @ 5m) × 28.5m (3 bays @ 9.5m); Height: ~36m | 300×600–450×800mm Beams; 300×600–400×400mm Columns | Ductile – Side-sway collapse |
| S1-M (Hi) | 4 (+1) | Irregular Plan: 48.5m (typ. 4.5m bays) × 9.5m (2.5m & 7m bays) + 28.5×7m + 4.5×12m; Height: 16.3m | W12×72–W12×96 Beams & W12×106–W12×150 Columns (Concrete Encased) | Based on Computational Philippine fragility (UPD-ICE); Residual plastic drifts; Possible broken weld connections |

**Secondary – Simplified:**

| Archetype ID | Stories | Avg. Floor Area | System | Possible Failure Modes |
|-------------|---------|----------------|--------|----------------------|
| CWS-L | 2 | 600 m² | RCMRF w/ wood frame | Based on Heuristic or Empirical Philippine fragilities (UPD-ICE) |
| S3-L | 1 | 110 m² | Light steel frame & bracing | Based on Heuristic or Empirical Philippine fragilities (UPD-ICE) |
| CHB-L | 1 | 100 m² | Reinforced/unreinforced CHB | Collapse driven; CHB/infills likely to collapse (in-plane/out-of-plane) |
| W-L | 1 | 369 m² | Wood frame and walls | Collapse driven; W-L & CWS-L more resilient (light-weight) |
| N-L | 1 | 145 m² | Wood frame w/ CHB/G.I. | Collapse driven |

*Notes: C1-H (Hi) includes 1 Basement + 1 Roof Deck Penthouse; S1-M (Hi) includes 1 Roof Deck Penthouse.*

---

## 5.2 Non-Linear Modelling Methodology of Primary Archetypes

### 5.2.1 Linear Elastic Model in SAP2000

SAP2000 (CSI, 2017) linear elastic models were developed first to:
1. Estimate seismic demands on elements for non-linear hysteretic property definition.
2. Determine column axial-flexural interaction surfaces.
3. Export geometries for PERFORM-3D.

Key modelling decisions:
- First-floor columns include additional unsupported length (1.1–1.5m) between top of slab-on-grade and centre of footing; fully fixed at base.
- Rigid-diaphragm constraints at each storey; flexible diaphragm at roof level (steel trusses).
- Beam-column joints modelled with default rigid end zones.
- Material properties from collected drawings; lower bound properties per ASCE-41.
- Effective flange widths per ASCE-41 with corresponding minimum slab reinforcement.
- Stiffness modifiers for cracked sections: IDR = 0.002 (service level) and 0.008 (design/MCE level).
- Fiber sections with 16 fibers (confined) and 12 (unconfined) using Mander-Parametric model.
- Non-linear stress-strain for rebar using Simple-Parametric model with Caltrans default strain values.
- ASCE-41 linear load combination; gravity loading converted to equivalent beam loads.

### 5.2.2 Non-Linear Modelling in PERFORM-3D

PERFORM-3D (CSI, 2011) receives geometries, masses, and element gravity loads from SAP2000. Lumped plasticity compound line elements with ASCE-41-based backbone curves (in terms of plastic end rotations).

**5.2.2.1 Ductile Beam-Columns**
- Beams: FEMA-Beam:Concrete elements — elastic RC beam bounded by zero-length chord-rotation rigid plastic hinges at column face and panel zone. Two FEMA-Beams per compound component with equal relative lengths at anticipated inflection point.
- ASCE-41 backbone includes plastic rotation capacities; both force-controlled and deformation-controlled actions considered. Collapse Prevention (CP) level acceptance criteria included.
- Columns: FEMA-Column:Concrete elements with coupled axial-bending behaviour through P–M2–M3 interaction surface. Yield surface defined by SAP2000 fiber models considering confinement. Shape factors adjusted for C1-M (Hi) and C1-L (Hi) to prevent excessive inelastic tensile deformations; C1-M (Mid) left as-is.
- Final choice: lumped plasticity chord-rotation model over fiber model — better alignment with ASCE-41 NSP results; ASCE-41 backbones implicitly account for cyclic degradation. Bar slip not expected to be significant.

**5.2.2.2 Non-Ductile Beam-Columns (C1-M Pre/Lo)**
- Inelastic shear behaviour modelled with uncoupled rigid-plastic displacement-type shear hinges in PERFORM-3D.
- Shear hysteresis backbone from Zimos et al. (2015), following O'Reilly (2016) approach for non-ductile Italian RC frames.
- Effective elastic shear stiffness applied until peak shear strength; backbone control points (γ_u,cr, γ_u,res) and degrading shear stiffnesses calculated by empirically-calibrated predictor variables.
- Residual shear strength: empirical equation by LeBorgne and Ghannoum (2014).
- Short-column effects simulated via eccentrically-braced frame analogy; eccentric infills produce mid-height shear hinges with shear hinge length = distance between two plastic hinge segments (L_cl − 2L_p).
- Bi-axial shear interaction (V2–V3) with default factor 2.0.

**5.2.2.3 FRP-Retrofitted Beam-Columns (C1-M Pre/Lo FRP)**
- Shear hinges removed; same modelling as ductile beam-columns.
- Additional confinement from FRP column jacketing: equivalent jacket diameter (D_eq) and lateral confinement pressure (f_l,a) per ACI-440 (2017) and Alvarez (2017).
- Updated P–M–M yield surfaces and moment-curvature relationships.
- Capping plastic rotations (θ_cap) for FRP-retrofitted columns from Li and Harries (2018).
- Post-capping plastic rotations and residual strength ratios from ASCE-41 for code-conforming RC columns.

**5.2.2.4 Joints**
- Zero-length elastic Default End Zone components at column compound element ends.
- Joint stiffness set to 10× stiffer than surrounding columns and beams.
- C1-M (Pre/Lo) uses same technique as ductile counterparts (re-design implemented proper confinement throughout joint).

**5.2.2.5 CHB Infill**
- CHB walls: 150mm thick solid non-perforated walls only; 100mm and perforated walls ignored.
- Modelled as 1D Inelastic Concrete Material compression-only struts (Inelastic Concrete Strut components in PERFORM-3D).
- ASCE-41 infill wall backbone and CP acceptance criteria in terms of IDRs and shear strength (V_in,max) converted to equivalent axial compressive strengths and strains.
- Residual strength of infill struts set to 10% of maximum axial compressive capacity (ASCE-41 was deemed to overestimate this).
- **Concentric struts** (pin-connected at joints) for High-Code archetypes.
- **Eccentric struts** for Mid- and Low-Code archetypes — connected at distance from joints equal to column plastic hinge length (L_p) to simulate short-column effects.
- Shear strength from ASCE-41 (2017), NZSEE (2017), TMS 402 (MSJC, 2011).
- CHB infill struts isolated (removed) in C1-M (Pre/Lo) FRP model — saw-cut gap simulated.
- Out-of-plane effects not modelled; capacities determined from NZSEE (2017) and ASCE-41.

**5.2.2.6 Diaphragms**
- RC slabs: rigid diaphragms at each floor level.
- Roof level: flexible diaphragm — steel roof trusses (ASTM A36 double angles + A653SQGr33 cold-formed purlins) modelled in SAP2000; equivalent shear stiffness implemented in PERFORM-3D as Linear Elastic Infill Panel components.
- C1-M (Pre/Lo): lightweight timber truss at roof; not explicitly modelled. Flexible diaphragm not used at roof level for this archetype.

**5.2.2.7 Global Modelling Properties**
- RC columns fully fixed at base; tie-beams provide sufficient stiffness to neglect foundation modelling.
- SSI effects: structure-to-soil-stiffness ratio R_ss < 0.1 (except one archetype slightly at 0.11); SSI deemed negligible.
- Rayleigh damping: 2.5% damping ratio at 0.25T₁ and 1.5T₁.
- P-delta geometric nonlinearity turned on for columns.
- 3 mode shapes per storey calculated.

---

## 5.3 Archetypal Non-Linear Seismic Response

### 5.3.1 Non-Linear Static Pushover (NSP)

Pushover analyses conducted in both principal axes per ASCE-41 (2017) NSP using mode shapes at directional fundamental periods.

**Table 5-4:** Summary of NRHA archetype properties (printed p. 87):

| Parameter | C1-L (Mid/Hi) | C1-M (Hi) | C1-M (Mid) | C1-M (Pre/Lo) | C1-M (Pre/Lo) FRP |
|-----------|--------------|----------|-----------|--------------|------------------|
| Stories | 2 | 4 | 3 | 3 | 3 |
| T₁ = T_Long. [s] | 0.49 | 0.67 | 0.59 | 0.50 | 0.46 |
| T_Trans.,Infill [s] | 0.24 | 0.53 | 0.36 | 0.33 | — |
| T_Long.,Bare [s] | 0.47 | 0.69 | 0.55 | 0.47 | 0.44 |
| T_Trans.,Bare [s] | 0.25 | 0.49 | 0.361 | 0.34 | 0.42 |
| Weight, W [kN] | 3,320 | 9,210 | 8,210 | 8,160 | 8,160 |
| V_y,Long. [kN] | 1,750 | 4,100 | 4,000 | 3,540 | 4,880 |
| V_max,Long. [kN] | 2,010 | 4,710 | 4,450 | 4,070 | 5,600 |
| V_y,Trans. [kN] | 2,110 | 4,740 | 4,110 | 3,660 | 5,710 |
| V_max,Trans. [kN] | 2,510 | 5,640 | 4,720 | 4,360 | 6,800 |

*Note: Long.=Longitudinal; Trans.=Transverse; Bare = T without infill. CHB infills cause 2nd period (T₂) to be dominated by torsional response for C1-L (Mid/Hi), C1-M (Mid), and C1-M (Pre/Lo).*

Target roof displacement (δ_t) determined from pushover curves and elastic response spectra (Chapter 3), converting elastic SDOF spectral displacements to inelastic MDOF roof displacements. NSP identified as **invalid** for C1-M (Pre/Lo) in both directions (μ_max > μ_lim due to non-ductile mechanisms). Similarly invalid for C1-L (Mid/Hi) transverse direction due to weak-beam-strong-column mechanism. IDR at δ_t underpredicted NRHA PIDR by 44–80% for all archetypes except C1-M (Hi).

### 5.3.2 Non-Linear Dynamic Time History Analyses (NLD/NRHA)

ASCE-41 (2017) Non-linear Dynamic Procedure (NDP) used. Key implementation details:
- Randomized input GM angles relative to principal axes — simulates random building orientation relative to West Valley Fault; reduces bias from maximum-direction GM component.
- Records padded with 10s to ensure steady-state for accurate RIDR determination.
- GM suites: 5 intensity levels (75-, 175-, 475-, 975-, 2,475-year return periods) for both Soil C and Soil D.
- Collapsed records excluded from EDP summaries.

**5.3.2.1 Failure Modes and Local Response:**
- **C1-M (Hi):** Appropriate strong-column-weak-beam; beam hinging before column hinging. Column hinging in 2nd and 3rd stories began as beam yielding occurred in all stories except roof. Considered ductile behaviour.
- **C1-M (Mid) and C1-L (Mid/Hi):** More severe column hinging than beam hinging, particularly in hallway bay — weak-column-strong-beam behaviour.
- **C1-M (Pre/Lo):** Collapsed upon column shear hinging and force redistribution failure (model convergence failure with 400–500 nonlinear events per time-step). Beam flexural hinging occurred before column hinging.
- **C1-M (Pre/Lo) FRP:** Beam hinging first; at higher intensities, 2nd storey beam hinge slightly exceeded ground floor column hinge degradation. Damage isolated below 2nd storey beams even at highest intensity. No shear failure.

**5.3.2.2 Global Response (EDPs):**
EDPs post-processed: Peak Inter-Storey Drift Ratios (PIDR), Residual Inter-Storey Drift Ratios (RIDR), Peak Floor Accelerations (PFA), Peak Floor Velocities (PFV).
- EDPs presented as figures (Figure 5-20 through 5-24) for Soil D suites at 75-, 475-, 2,475-year return periods; Soil C EDPs in Appendix C.5.6.
- EDP summary statistics are graphical only — no separate tabulated summary tables for EDP medians/dispersions per archetype per intensity are provided in the thesis body.

Key narrative observations:
- **C1-M (Hi):** Mean lower-storey PIDRs of 1.5–2% at maximum intensity (2,475-yr). Mean RIDRs generally below 1% limit. PFAs ~0.25–1g on lower floors at 475–2,475-year, ~2g at roof level.
- **C1-L (Mid/Hi) and C1-M (Mid):** Maximum intensity PIDRs in range 1.25–2.5%; RIDRs < 1% for all but maximum intensity. PFAs for C1-L (Mid/Hi): 0.5–1.25g; C1-M (Mid): 0.25–0.75g for 2nd/3rd stories, 0.75–1.25g at roof.
- **C1-M (Pre/Lo):** Numerous collapses rendered EDPs unusable for all but one record at 2,475-year Soil D; that single surviving record EDP comparable to mean of C1-M (Mid).
- **C1-M (Pre/Lo) FRP:** FRP retrofit improved PIDR and RIDR; did not significantly change PFA and PFV vs. Pre/Lo.
- Modelled RIDRs were 1.2–1.6× higher than FEMA P-58 (2018a) simplified method estimates.

### 5.3.3 Collapse Fragilities (NRHA Archetypes)

Collapse Multiple Stripes Analysis (MSA) conducted using all five intensities and both soil suites. Additional GM suites prepared by scaling the 2,475-year Soil D GM suite by factors of 1.1–2.5 to achieve collapses in all records.

**Collapse indicators:**
1. Column P–M2–M3 hinge plastic rotations conservatively reaching CP level acceptance criteria.
2. Column shear hinge displacements reaching CP level.
3. PIDR exceeding 10% (non-simulated collapse indicator — most common mode for all except C1-M Pre/Lo).

Log-normal Maximum Likelihood Estimation (MLE) fit to number of collapses per GM suite (Baker, 2015 methodology). Collapse fragilities conditioned on suite mean spectral acceleration at average of directional periods, S_a(T_avg).

**Collapse fragility parameters from MSA-MLE (Figure 5-25, printed p. 105):**
The figure shows lognormal collapse fragility curves. Numerical values are tabulated in Table 6-6 (Chapter 6) after enrichment with modelling uncertainty:

| Archetype | T_avg [s] | θ_Sa(Tavg) [g] | β_Sa(Tavg) (combined) | Method | β_m (modelling uncertainty) |
|-----------|-----------|----------------|----------------------|--------|---------------------------|
| C1-M (Hi) | 0.65 | 2.00 | 0.09 | NRHA-MSA | 0.47 |
| C1-M (Mid) | 0.45 | 1.72 | 0.17 | NRHA-MSA | 0.57 |
| C1-M (Pre/Lo) | 0.40 | 1.11 | 0.23 | NRHA-MSA | 0.57 |
| C1-M (Pre/Lo) FRP | 0.47 | 2.12 | 0.21 | NRHA-MSA | 0.57 |
| C1-L (Mid/Hi) | 0.37 | 1.85 | 0.15 | NRHA-MSA | 0.47 |

*Key observation from thesis: collapsed median (θ) of C1-M (Pre/Lo) was almost doubled by the FRP shear retrofitting.*

*Note: Dispersions (β) in Figure 5-25 shown before enrichment with modelling uncertainty in Chapter 6. The combined β values in Table 6-6 (above) include β_m.*

---

## 5.4 Simplified Models

Simplified FEMA P-58 (2018a) models developed for secondary and primary non-NRHA archetypes. Philippine-specific UPD-ICE (Pacheco et al., 2014) fragilities (in terms of PGA) converted to equivalent HAZUS models (in terms of spectral quantities).

**Conversion approach:**
- HAZUS equivalents selected for secondary archetypes to match UPD-ICE PGA-based "Complete" fragility curves.
- C1-H (Hi): HAZUS High-Code pushover properties selected directly.
- S1-M (Hi): UPD-ICE computational pushover curves (Pacheco et al., 2014) used directly.
- Yield base shear strength (V_y) and yield roof displacement (δ_roof,y) calculated with local building height (h_roof), weight (W), and code-based fundamental period (T_code).

**Table 5-5:** Summary of simplified model properties (printed p. 106–107):

| Parameter | W-L | N-L | CHB-L | S3-L | C1-L (Pre/Lo) | C1-H (Hi) | S1-M (Hi) | CWS-L |
|-----------|-----|-----|-------|------|---------------|-----------|----------|-------|
| Stories | 1 | 1 | 1 | 1 | 2 | 11ᵃ | 5ᵃ | 2 |
| h_roof [m] | 4.0 | 4.0 | 4.0 | 4.0 | 6.9 | 36.0 | 16.3 | 6.9 |
| Total Floor Area [m²] | 369 | 145 | 100 | 110 | 599 | 17,577 | 2,783 | 599 |
| W [kN] | 111 | 29 | 236 | 138 | 3,715 | 191,849 | 30,767 | 2,786 |
| T_code [s] | 0.14 | 0.14 | 0.14 | 0.14 | 0.30 | 1.32 | 0.84 | 0.30 |
| HAZUS Equivalent | W1-L (Pre) | ~W1-L (Pre) | URM-L (Pre) | S3-L (Low) | C1-L (Pre) | C1-H (High) | S1-M (High) | C1-L (Mid) |
| V_y [kN] | 17 | 4 | 24 | 10 | 184 | 15,041 | 3,840 | 279 |
| δ_roof,y [m] | 0.01 | 0.01 | 0.01 | 0.00 | 0.00 | 0.07 | 0.05 | 0.01 |
| R (ductility) | 2 | 1 | 1.5 | 3.5 | 3 | 8 | 8 | 3 |
| θ_Sa(T) [g] (collapse median) | 0.75 | 0.47 | 0.35 | 1.01 | 1.00 | 2.72 | 4.26 | 2.10 |
| β_Sa(T) (collapse dispersion) | 0.94 | 0.94 | 0.94 | 0.94 | 0.94 | 0.90 | 0.90 | 0.94 |

*Notes: ᵃ Includes roof deck penthouse. V_max ranges for C1-L (Pre/Lo): 6,408–6,874 kN; CWS-L: 4,806–5,156 kN; S1-M (Hi): 31,710–51,355 kN; C1-H (Hi): 124,645 kN (range dependent on site class).*

**Collapse median derivation for low-rise simplified archetypes:** UPD-ICE "Complete" fragilities converted to short-period spectral accelerations S_a (for 0.11 < T < 0.55s) estimated as 2.5× PGA (per ASEP, 2016). High-Code primary archetypes C1-H (Hi) and S1-M (Hi) adopted judgement-based collapse fragilities. All simplified collapse dispersions assigned high values (β = 0.90–0.94) to account for increased uncertainty.

**EDP generation approach:**
- ASCE-41 pseudo-static lateral force V_ps,n applied at each intensity n based on first mode response.
- Linear-elastic HAZUS segment used to calculate equivalent spectral displacement S_d,n from S_a(T_code).
- Soil C target spectra used for all simplified archetypes except C1-L (Pre/Lo) and S1-M (Hi) which also used Soil D.
- Roof displacement δ_roof,n calculated from S_d,n; first mode shape assumed for floor displacement/drift.
- P-58 non-linear response correction factors applied to drift estimates.
- P-58 approximations used for RIDR, PFA, PFV.
- Dispersions assigned from default P-58 values (already include β_m).

**Cautions:** The simplified method was developed for regular ductile buildings (FEMA, 2018a) and is unlikely to be fully applicable to non-engineered secondary archetypes. These archetypes exhibit high collapse probabilities and account for a small fraction of the building stock.

---

## 5.5 Concluding Remarks

Chapter 5 presented the methods for developing representative building fragilities for all portfolio archetypes. Key deliverables:
- Structural re-designs of C1-M (Pre/Lo) and C1-M (Mid) using vintage NSCP editions.
- Detailed non-linear PERFORM-3D models for four primary RCMRF archetypes and one proposed FRP retrofit.
- NSP results and NRHA-derived global building responses (EDPs) and local failure modes for 5 modelled archetypes.
- Collapse fragilities from MSA-MLE for NRHA archetypes; simplified collapse fragilities from HAZUS/UPD-ICE conversion for remaining archetypes.
- EDPs and collapse fragilities assembled for all archetypes for use in the Chapter 6 loss estimation.

Key limitations acknowledged:
- Limited calibration/validation of individual element response; detailed OpenSees models with element-level validation recommended for future work.
- RIDR from NRHA was 1.2–1.6× higher than P-58 simplified method estimates.
- PFA spikes from abrupt stiffness changes in non-linear systems (Wiebe & Christopoulos, 2010; 2011) — not expected to significantly impact overall loss estimation given limited acceleration-sensitive elements.
- Simplified method less reliable for non-engineered secondary archetypes.

---

*Chapter boundary: PDF pages 92–136; Printed pages 65–109.*
*Extraction confidence: HIGH — all major tables, periods, fragility parameters, and modelling decisions captured from text.*
