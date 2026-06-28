# Chapter 7: Portfolio-Wide Loss Estimation

**Source:** Jeswani, Kevin Kamlesh (2021). *The Seismic Resilience of Critical Spatially-Distributed Building Portfolios.* MASc Thesis, University of Toronto. Chapter 7 (printed pp. 152–183; PDF pp. 179–210).

---

## 7.0 Introduction

Chapter 7 compiles seismic hazard information (Chapter 3), the building exposure database (Chapter 4), and intensity-based normalized vulnerabilities (Chapter 6) to: (i) select rupture scenarios, (ii) define portfolio building properties, (iii) assign representative vulnerabilities to each building, and (iv) run a scenario-based portfolio risk analysis. Key portfolio loss distributions are presented for the maximum credible West Valley Fault (WVF) Mw=7.3 event; other scenarios are given in Appendix E.

---

## 7.1 Portfolio Loss Estimation Methodology

The methodology was originally presented in Guo et al. (2018). A Monte Carlo analysis is conducted with **R = 1000 realizations** per rupture scenario.

### 7.1.1 One-Iteration Flow (Figure 7-1)

For each realization j:
1. Random numbers r_1,...,r_N are generated to sample probabilistic decision variable (DV) distributions.
2. The intensity measure Sa(T1) is generated at each site i based on fault parameters (Mw, Lrup, Wrup, Ztor) and site-source distance parameters (Rjb, Rrup).
3. A random sampling of the GMPE determines spectral acceleration demands at each site, accounting for Vs30.

### 7.1.2 Spatial Correlation Model

To consider **"within-event" spatial variation**, the spatial correlation function of **Loth and Baker (2013)** is incorporated. This represents the intra-event residual — the standard deviation of the natural log of uncertainty in ground-motion demand between sites. The Loth and Baker (2013) model:
- Links spectral accelerations across **multiple periods and site-site distances**
- Was developed with Californian and Taiwanese records
- Sa(T1) is the selected fragility IM
- Overall results are highly dependent on spatial correlation and IM selection (Baker et al., 2008; Du et al., 2020)
- The authors note this model was deemed applicable but that further validation in the Philippine context would be needed

### 7.1.3 Loss Computation (EQ 7-1)

Once Sa(T1) is determined at site i, building loss is computed by:

    [k]           [k]
L  ,ij = F_inv( p  ,ij | IM = im_ij )                    [EQ 7-1]

Where:
- L^[k] is the k-th consequence in the loss vector (one per DV: monetary loss, downtime, injuries, fatalities)
- L^[k]_{i,j} is the k-th consequence for site i in realization j
- F is the normalized vulnerability "surface" (conditional probability distribution for losses given IM)
- p^[k]_{i,j} is a random sample of probability of non-exceedance

Loss is determined by taking the inverse of conditional loss distribution F, mapping probability of non-exceedance to a loss value. Each DV is determined independently — EDPs and damage states are **not computed at the portfolio level**. DVs are aggregated across all sites per realization to produce the probabilistic portfolio loss distribution.

---

## 7.2 Rupture Scenarios

### 7.2.1 Scenario Selection (Section 7.2.1)

Five rupture scenarios were selected (Table 7-1, printed p. 155):

| ID | Fault Name | Tectonics | Mw | delta_avg (°) | lambda (°) | Wrup (km) | Lrup (km) | Ztor (km) | Zhyp (km) | Epicenter Lat | Epicenter Lon |
|----|-----------|-----------|-----|--------------|-----------|----------|----------|----------|----------|--------------|--------------|
| A | Marikina West Valley (WVF) | Crustal: Dextral-Normal | 6.5 | 75 | -120 | 12 | 25 | 0 | 8 | 14.65° | 121.09° |
| B | Marikina West Valley (WVF) | Crustal: Dextral-Normal | 7.3 | 75 | -120 | 21 | 99 | 0 | 12 | 14.65° | 121.09° |
| C | Marikina East Valley (EVF) | Crustal: Normal | 6.9 | 65 | -90 | 20 | 36 | 0 | 11 | 14.74° | 121.17° |
| D | General Nakar West (GNW) | Crustal: Sinistral | 7.6 | 90 | 0 | 22 | 101 | 0 | 12 | 15.01° | 121.35° |
| E | Manila Trench | Subduction Interface | 7.9 | 30 | 90 | 127 | 201 | 9 | 25 | 14.43° | 119.89° |

**Note on Mw discrepancy:** Table 7-1 (the definitive parameter table) shows Mw=7.6 for GNW (D) and Mw=7.9 for Manila Trench (E). However, the body text in Section 7.2.1 references the GNW as "Mchar of M=7.2" and Manila Trench as "Mw=8.15," and Appendix E figure headings use "GNW Mw=7.2" and "MNLT Mw=8.15." This discrepancy is unresolved in the thesis. The Appendix E figure labels (Mw=7.2 and Mw=8.15) likely reflect the characteristic magnitudes used for scenario identification/naming, while Table 7-1 may reflect slightly different parameterization. The Mw values in Table 7-1 (7.6 and 7.9) are what was actually input to the GMPEs in simulation. **REVIEW NEEDED** — see validation YAML notes.

**Scenario rationale:**
- WVF scenarios align with GMMA-RAP (Allen et al., 2014): most probable Mw=6.5 event and maximum size Mw=7.3
- EVF: Mmax = 6.6 per Peñarubia et al. (2020) — Table 7-1 shows Mw=6.9 used in simulation
- GNW: Far-field (30-45 km away) shallow crustal scenario
- Manila Trench: Far-field subduction interface scenario, central "segment 2" in PEM2020
- Selections align with disaggregation from Dungca and Chua (2016): WVF and EVF govern at all return periods

### 7.2.2 Fault Parameter Definition

- Fault dips (delta) and mechanisms from GAF database (GEM, 2020a)
- Rake (lambda) ranges from Kaklamanos et al. (2011)
- Upper seismogenic depth (Ztor): 0 km for shallow crustal; 9 km for Manila Trench subduction interface
- Lower seismogenic depth: 20 km for crustal; 50 km for subduction
- Rupture lengths/widths from Leonard (2010) area-magnitude scaling (crustal) and Thingbaijam et al. (2017) (Manila Trench)
- Median normalized hypocentral depth ratios: 0.6 (dip-slip crustal) and 0.4 (subduction interface), per Mai et al. (2005)
- Site-source distances Rjb and Rrup computed per Kaklamanos et al. (2011)

**Distance parameter ranges (Table 7-2, printed p. 157):**

| ID | Fault Name | Mw | Rjb (km) | Rrup (km) |
|----|-----------|-----|---------|----------|
| A | WVF | 6.5 | 0-9.5 | 0-9.5 |
| B | WVF | 7.3 | 0-9.5 | 0-9.5 |
| C | EVF | 6.9 | 2.9-20.0 | 2.9-20.0 |
| D | GNW | 7.6 | 10.9-45.8 | 29.7-45.8 |
| E | Manila Trench | 7.9 | 105.6-124.7 | 100.6-117.6 |

### 7.2.3 GMPEs Used (Table 7-3, printed p. 158)

Following Peñarubia et al. (2020) (PEM2020), equal weights of 0.25 applied to four GMPEs per fault type:

**Shallow Crustal:** Chiou & Youngs (2008), Boore & Atkinson (2008), Zhao et al. (2006), Boore et al. (2014)

**Subduction Interface:** Youngs et al. (1997), Atkinson & Boore (2003), Zhao et al. (2006), Abrahamson et al. (2016)

**Directivity:** Average directivity model (Shahi & Baker, 2013) applied to near-fault WVF and EVF scenarios.

---

## 7.3 Scenario Results

### 7.3.1 Portfolio Definition

Portfolio: Makati City and Quezon City public school building portfolio.

**Total Replacement Costs:**
- Makati: PHP 10.6 bil.
- Quezon City: PHP 20.0 bil.

**Total Populations (as of 2016/2017):**
- Makati: ~94,300 students
- Quezon City: ~466,000 students

**Preliminary FRP Retrofit Cost Estimates (PTC1-M (Pre/Lo) and C1-M (Pre/Lo) buildings):**
- Makati: PHP 0.46 bil. (4.4% of replacement cost)
- Quezon City: PHP 0.54 bil. (2.7% of replacement cost)

**Non-structural Upgrade Estimates:**
- Makati: PHP 425 mil. (4.0% of replacement cost)
- Quezon City: PHP 835 mil. (4.1% of replacement cost)

### 7.3.2 Vulnerability Surfaces and Monte Carlo Analysis

- 4 normalized DV vulnerability "surfaces" assigned per archetype (monetary loss, downtime, injuries, fatalities)
- R = 1000 Monte Carlo realizations per scenario
- 10 total portfolio analyses (5 scenarios × existing + mitigated)
- Mitigated: archetypal vulnerabilities replaced with mitigated counterparts wherever applicable

### 7.3.3 Barangay Risk Factor

A composite barangay risk factor was developed overlaying:
- Proportion of floor area in collapsed/complete-damage buildings (from GMMA-RAP Mw=7.2 WVF damage data)
- Informal (N-L typology) housing densities
- 2015 Census population densities (adjusted by land area)

Weights: {population (br_p), informal settlements (br_i), building collapses (br_c), complete damage (br_cd)} = {0.3, 0.4, 0.4, 0.3}

### 7.3.4 West Valley Fault (WVF) Mw=7.3 — Governing Scenario

Mean of R=1000 simulated Sa(0.5s) realizations shown in Figure 7-3.

**Primary resilience metric: Time to 90% portfolio Functional Recovery** (selected over 100% due to significant difference in Makati driven by two C1-H (Hi) buildings).

---

## 7.4 Discussion of Results (WVF Mw=7.3 Base Case)

### 7.4.1 Monetary Loss

**WVF Mw=7.3 — MAKATI (Existing/Base Case):**
- {Median, 90th percentile} = PHP {2.8, 4.5} bil.
- Loss ratios: {0.26, 0.42}

**WVF Mw=7.3 — QUEZON CITY (Existing/Base Case):**
- {Median, 90th percentile} = PHP {6.2, 9.4} bil.
- Loss ratios: {0.31, 0.47}

**Comparison context:** Gilani & Miyamoto (2017) found loss ratios ~0.8 for entire Metro Manila public school portfolio; difference attributed to their more conservative US-based fragility functions and higher proportion of Soil D sites.

**Downgraded scenario (replicating Gilani & Miyamoto procedure, lower-bound estimate):**
- Makati: {Median, 90th percentile} loss ratios = {0.40, 0.60}
- Quezon City: {Median, 90th percentile} loss ratios = {0.38, 0.57}

**After structural mitigation (Makati):**
- {Median, 90th percentile} loss ratios = {0.18, 0.33}

**Note:** C1-M (Pre/Lo) = largest relative share of loss in Makati; C1-L (Pre/Lo) = largest share in Quezon City.

### 7.4.2 Injuries

**WVF Mw=7.3 — MAKATI (Existing/Base Case):**
- {Median, 90th percentile} injuries = {13,650, 19,500}
- Injury ratios = {14.5%, 20.7%}
- Non-collapse injuries = 78–99% of total (existing); 33–69% (mitigated)

**WVF Mw=7.3 — QUEZON CITY (Existing/Base Case):**
- {Median, 90th percentile} injuries = {1,000, 2,500} (Note: these appear low relative to QC population; likely reflect lower Soil D exposure near WVF)
- Injury ratios = {9.1%, 11.7%}  ← per-building ratios, not total campus ratios

Note: Section 7.4.2 says "1000, 2500 in Quezon City" but Figure 7-14 CDF shows the x-axis extends to ~60 (×1000) suggesting different scale — text confirms these are ratios. Injury count from Figure 7-14 appears higher (~2,000–5,000 range at median reading). **The text values are authoritative.**

**After non-structural mitigation:**
- Makati: {Median, 90th percentile} injury rates = {1.1%, 2.6%}
- Quezon City: {Median, 90th percentile} injury rates = {2.3%, 3.1%}

### 7.4.3 Fatalities

**WVF Mw=7.3 — MAKATI (Existing/Base Case):**
- {Median, 90th percentile} fatalities = {320, 950}
- Fatality ratios = {0.3%, 1.0%}

**WVF Mw=7.3 — QUEZON CITY (Existing/Base Case):**
- {Median, 90th percentile} fatalities = {900, 2,500}
- Fatality ratios = {0.2%, 0.3%}

Non-collapse fatalities essentially null (all but one component assumed to have no fatality consequence in damage states). FEMA P-58 (2018a) collapse fatality rates used.

**After structural mitigation:**
- Makati: {Median, 90th percentile} fatality rates = {0.04%, 0.2%}
- Quezon City: {Median, 90th percentile} fatality rates = {0.1%, 0.2%}

### 7.4.4 Portfolio Recovery

**WVF Mw=7.3 — Time to 90% Functional Recovery (FR):**
- Makati: {Median, 90th percentile} = {970, 1070} days
- Quezon City: {Median, 90th percentile} = {640, 655} days

North American REDi values used — results subject to further review. Recovery times counterintuitive (Makati longer despite less restrictive residual drift constraint) due to large building replacement times.

**Student Disruptions (in student-days):**
- Product of Functional Recovery time × assigned population per building
- Results mapped in Figures 7-6 through 7-21

### 7.4.5 Spatial Observations

- Makati areas A1–A4 (Figure 7-8): moderate to high barangay risk with significant campus injuries and fatalities
- Makati area A5 (Figure 7-12): recovery times 600–800 days; moderate to high barangay risk
- Quezon City area A1 (Figure 7-17, 7-19): large dense cluster of injuries/fatalities near WVF
- Quezon City area A4 (Figure 7-21): recovery times 500–800 days
- General: losses concentrated near WVF and on Soil D sites

---

## 7.5 Concluding Remarks

The Guo et al. (2018) methodology enabled computationally efficient seismic risk analysis of a spatially distributed building portfolio. Five fault rupture scenarios spanning near-fault and far-field hazards were analyzed. Mitigations showed greatest benefit in Makati (structural retrofit of C1-M Pre/Lo). The WVF Mw=7.3 scenario governs all portfolio loss metrics.

---

## Key Parameter Summary

| Parameter | Value |
|-----------|-------|
| Monte Carlo realizations (R) | 1000 |
| Intensity measure (IM) | Sa(T1) = Sa(0.5s) |
| Spatial correlation model | Loth & Baker (2013) |
| Spatial correlation type | Within-event (intra-event residual) |
| Loss computation method | Inverse CDF sampling of vulnerability surface |
| Primary resilience metric | Time to 90% Functional Recovery |
| DVs computed | Monetary loss, downtime (functional recovery), injuries, fatalities, student-days |
| Portfolio: Makati total replacement cost | PHP 10.6 bil. |
| Portfolio: QC total replacement cost | PHP 20.0 bil. |
| Portfolio: Makati population (2016/17) | ~94,300 |
| Portfolio: QC population (2016/17) | ~466,000 |

---

## References Used in Chapter 7

- Guo, et al. (2018) — Portfolio loss methodology
- Loth & Baker (2013) — Spatial correlation model **[CONFIRMED]**
- Baker et al. (2008) — Sensitivity of portfolio results to IM and spatial correlation
- Du et al. (2020) — Sensitivity of portfolio results
- Allen et al. (2014) — GMMA-RAP
- Peñarubia et al. (2020) — PEM2020, fault Mchar and GMPEs
- Leonard (2010) — Area-magnitude scaling
- Thingbaijam et al. (2017) — Manila Trench scaling
- Kaklamanos et al. (2011) — Distance parameters
- Mai et al. (2005) — Hypocentral depth ratios
- Shahi & Baker (2013) — Average directivity model
- Gilani & Miyamoto (2017) — Metro Manila school loss comparison
- GEM (2020a) — GAF database
- Chiou & Youngs (2008), Boore & Atkinson (2008), Zhao et al. (2006), Boore et al. (2014) — Crustal GMPEs
- Youngs et al. (1997), Atkinson & Boore (2003), Abrahamson et al. (2016) — Subduction GMPEs
- FEMA P-58 (2018a) — Collapse fatality rates
