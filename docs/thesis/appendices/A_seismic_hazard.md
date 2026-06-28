# Appendix A: Seismic Hazard Definition

**Thesis:** Jeswani, Kevin Kamlesh (2021). *The Seismic Resilience of Critical Spatially-Distributed Building Portfolios.*
**PDF pages:** 241–251 (printed pages 214–224)

---

## A.1 Metro Manila Historical Earthquakes & Active Faults

JICA et al. (2004) presented 18 earthquake scenarios and fault model parameters from different seismic generators around Luzon, Philippines.

### Table A-1: Metro Manila Seismic Generators (After: JICA et al., 2004)

| No. | Fault Name | Tectonics | Mw | Dist. (km) | Fault Length/Width (km) | Dip Angle | Depth (km) | Past Earthquakes (Y.M.D / Ms) |
|-----|-----------|-----------|-----|-----------|------------------------|-----------|-----------|-------------------------------|
| 1 | PFZ: Digdig Segment | C-SS | 7.9 | 92 | 115/26 | 90 | 2 | 1645.11.30 / 7.9; 1990.07.16 / 7.8 |
| 2 | PFZ: Infanta Segment | C-SS | 7.6 | 62 | 125/27 | 90 | 2 | 1880.07.18 / 7.6 |
| 3 | PFZ Ragay Gulf Segment | C-SS | 7.6 | 99 | 137/28 | 90 | 2 | 1824.10.26 / 7.4; 1973.03.17 / 7.3 |
| 4 | Casiguran Fault | S-R | 7.8 | 147 | 200/58 | 45 | 35 | 1968.08.01 / 7.3; 1970.04.07 / 7.3 |
| 5 | E-W Transform Fault | C-SS | 7.0 | 140 | 44/17 | 90 | 0 | 1970.04.12 / 7.0 |
| 6 | East Luzon Trough | S-R | 8.0 | 140 | 275/71 | 25 | 0 | — |
| 7 | (WVF scenario variant) | — | 6.8 | 3 | 30/15 | — | — | — |
| 8 | West Valley Fault | C-SS | 7.2 | 3 | 67/21 | 90 | 2 | 1658.08.19 / 5.7 |
| 9 | (WVF scenario variant) | — | 7.4 | 3 | 96/24 | — | — | — |
| 10 | East Valley Fault | C-SS | 6.3 | 8 | 10/9 | 90 | 2 | 1771.02.01 / 5.0 |
| 11 | Laguna-Banahaw Fault | C-SS | 7.5 | 45 | 56/19 | 90 | 2 | 1937.08.20 / 7.5 |
| 12 | West Boundary Fault | C-R | 7.5 | 91 | 120/42 | 90 | 0 | — |
| 13 | Manila Trench (16–14N) | S-R | 7.9 | 149 | 255/68 | 40 | 40 | 1677.12.07 / 7.3 |
| 14 | Manila Trench (14–12.5N) | S-R | 7.9 | 173 | 227/63 | 35 | 35 | 1972.04.25 / 7.2 |
| 15 | East Zambales Fault | C-SS | 7.4 | 76 | 110/26 | 90 | 2 | — |
| 16 | Lubang Fault | C-SS | 7.7 | 109 | 175/31 | 90 | 0 | 1942.04.08 / 7.5 |
| 17 | Central Mindoro Fault | C-SS | 7.5 | 124 | 116/26 | 90 | 2 | — |
| 18 | 1863 Earthquake | C-SS | 6.5 | 15 | 15/11 | 90 | 2 | 1863.06.03 / 6.5 |

**Notes:**
- C = Crustal; S = Subduction; R = Reverse; SS = Strike-Slip
- Wells & Coppersmith (1994) empirical formula used for earthquake magnitude potential and fault width from fault length
- Dip angle of subduction fault based on recent seismic activity; dip angle of crustal faults estimated to be vertical
- Distance taken from center of Metro Manila (14.5687°N, 121.0203°E)

---

## A.2 Ground-Motion Selection

Nine pulse-like and one non-pulse seed shallow crustal ground-motion (GM) records were selected from the NGA-West2 database (PEER, 2013) using the 2475-year T*S,a* (RotD100). Selection parameters included R = 0–35 km, Vs,30 range corresponding to each soil group, and period range T*min* to T*max*.

A weight function was applied across structural periods of interest 0.2T–3T (range 0.05–2 s for low- to mid-rise MRF suites), as recommended by NIST (2011).

### Table A-2: Selected Ground-Motion Seed Records – Soil D Group of Sites

| # | ID | Earthquake | Year | Station Name | Mw | Fault Type | Rrup (km) | Vs,30 (m/s) | AI (m/s) | Tp (s) |
|---|----|-----------|------|-------------|-----|-----------|----------|------------|--------|-------|
| 1 | R159 | Imperial Valley-06 | 1979 | Agrarias | 6.53 | C-SS | 0.65 | 242 | 1 | 2.34 |
| 2 | R723 | Superstition Hills-02 | 1987 | Parachute Test Site | 6.54 | C-SS | 0.95 | 349 | 3.7 | 2.39 |
| 3 | R764 | Loma Prieta | 1989 | Gilroy - Historic Bldg. | 6.93 | C-R | 10.97 | 309 | 0.7 | 1.64 |
| 4 | R900 | Landers | 1992 | Yermo Fire Station | 7.28 | C-SS | 23.62 | 354 | 0.9 | 7.50 |
| 5 | R1044 | Northridge-01 | 1994 | Newhall - Fire Sta | 6.69 | C-R | 5.92 | 269 | 5.7 | 1.37 |
| 6 | R1106 | Kobe, Japan | 1995 | KJMA | 6.9 | C-SS | 0.96 | 312 | 8.4 | 1.09 |
| 7 | R1176 | Kocaeli, Turkey | 1999 | Yarimca | 7.51 | C-SS | 4.83 | 297 | 1.3 | 4.95 |
| 8 | R1244 | Chi-Chi, Taiwan | 1999 | CHY101 | 7.62 | C-R | 9.94 | 259 | 3 | 5.34 |
| 9 | R1602 | Duzce, Turkey | 1999 | Bolu | 7.14 | C-SS | 12.04 | 294 | 3.7 | 0.88 |
| 10 | R6 | Imperial Valley-02 | 1940 | El Centro Array #9 | 6.95 | C-SS | 6.09 | 213 | 1.6 | — |
| 11 | UCS-VINA | Maule | 2010 | Vina del Mar - El Centro | 8.8 | SUB | 66.4 | 289 | 0 | — |

**Notes:** AI = Arias Intensity; C=Crustal, SS=Strike-Slip, R=Reverse, SUB=Subduction. Records in bold/blue are pulse motions. Source: NGA-West2 (PEER, 2013) for records 1–10; UCS RENADIC (2010) for record 11.

### Table A-3: Selected Ground-Motion Seed Records – Soil C Group of Sites

| # | ID | Earthquake | Year | Station Name | Mw | Fault Type | Rrup (km) | Vs,30 (m/s) | AI (m/s) | Tp (s) |
|---|----|-----------|------|-------------|-----|-----------|----------|------------|--------|-------|
| 1 | R451 | Morgan Hill | 1984 | Coyote Lake Dam - SW Abutment | 6.19 | C-SS | 0.53 | 561 | 3.9 | 1.07 |
| 2 | R802 | Loma Prieta | 1989 | Saratoga - Aloha Ave | 6.93 | C-SS | 8.5 | 381 | 1.5 | 4.57 |
| 3 | R828 | Cape Mendocino | 1992 | Petrolia | 7.01 | C-R | 8.18 | 422 | 3.8 | 3.00 |
| 4 | R982 | Northridge-01 | 1994 | Jensen Filter Plant Admin. Bldg | 6.69 | C-SS | 5.43 | 373 | 5.3 | 3.16 |
| 5 | R1148 | Kocaeli, Turkey | 1999 | Arcelik | 7.51 | C-R | 13.49 | 523 | 0.3 | 7.79 |
| 6 | R4065 | Parkfield-02, CA | 2004 | PARKFIELD - EADES | 6.0 | C-SS | 2.85 | 384 | 0.8 | 1.22 |
| 7 | R2734 | Chi-Chi, Taiwan-04 | 1999 | CHY074 | 6.2 | C-SS | 6.2 | 553 | 1.6 | 2.44 |
| 8 | R3473 | Chi-Chi, Taiwan-06 | 1999 | TCU078 | 6.3 | C-R | 11.52 | 443 | 1 | 4.15 |
| 9 | R4040 | Bam, Iran | 2003 | Bam | 6.6 | C-SS | 1.7 | 487 | 8 | 2.02 |
| 10 | R57 | San Fernando | 1971 | Castaic - Old Ridge Route | 6.61 | C-SS | 22.63 | 450 | 1 | — |
| 11 | UCS-ANTU | Maule | 2010 | La Pintana | 8.8 | SUB | 72.6 | 621 | 0 | — |

**Notes:** Same as Table A-2. Sources: NGA-West2 (PEER, 2013) for records 1–10; UCS RENADIC (2010) for record 11.

---

## A.3 Spectral Matching

### A.3.1 Procedure

Pulse-like records: the velocity time-histories v(t) of the largest identified pulse and corresponding azimuth rotation angle (θmax-dir) are extracted. The residual v(t) is differentiated to retrieve a(max-dir)(t), the maximum-direction component for spectral matching. The minimum-direction component a(min)(t) is derived by rotating at θmax-dir + 90°.

For non-pulse GM record pairs, the RotDSpectro script identifies the mode of Sa,RotD100 azimuth rotation angles between T = 0.4–1 s.

Bi-directional spectral matching was performed using RSPMatchBi script to match components to the target spectra (TSa,max and TSa,min) at each intensity for each soil group. A tolerance of 30–50% was applied across the broad-band period range T = 0.1–2 s.

### A.3.2 Change Measures

Spectrally-matched GM pairs were verified against NIST (2011) bounds:

### Table A-4: Summary of Change-Measures for Checking Spectrally-Matched GMs (After: NIST, 2011)

| Type | Parameter | Description | Lower Bound | Upper Bound |
|------|-----------|-------------|-------------|-------------|
| Peak Ground Motion | ΔPGA | Ratio of SM to AS peak ground acceleration | 0.4 | 1.9 |
| Peak Ground Motion | ΔPGV | Ratio of SM to AS peak ground velocity | 0.5 | 1.7 |
| Peak Ground Motion | ΔPGD | Ratio of SM to AS peak ground displacement | 0.5 | 3.8 |
| Cumulative Squared | ΔAI | Ratio of final Arias intensity values | 0.4 | 2.0 |
| Cumulative Squared | ΔCSV | Ratio of final cumulative squared velocity values | 0.4 | 2.7 |
| Cumulative Squared | ΔCSD | Ratio of final cumulative squared displacement values | 0.4 | 7.1 |
| Max diff. in normalized peak | max(ΔAI)norm | Max difference over time of Arias intensity (normalized to final value) | 0.0 | 0.2 |
| Max diff. in normalized peak | max(ΔCSV)norm | Max difference over time of CSV (normalized to final value) | 0.0 | 0.2 |
| Max diff. in normalized peak | max(ΔCSD)norm | Max difference over time of CSD (normalized to final value) | 0.0 | 0.4 |
| Input Energy | ΔIE | Replacement for input energy: (0.5·AI²tmax,SM) / (0.5·AI²tmax,AS); After Shiwua & Rutman (2014) | 0.6 | 1.9 |
| Pulse Period | ΔTp | Change in pulse-period (Pulse-ID script; Shahi & Baker, 2014) = Tp,SM / Tp,AS | 0.75* | 1.25* |

*Assumed bounds.

### A.3.3 Spectral Matching Results

Spectral matching of Soil D GMs required relaxation of the 30–50% tolerance threshold for certain record pairs. Scale factors for certain records were increased when re-adding the extracted pulse to satisfy the Pulse-ID algorithm. Results are shown in Figures A-2 (Soil D) and A-3 (Soil C).

---

## A.4 Liquefaction Potential

A liquefaction potential map for Metro Manila was provided by PHIVOLCS (2018), originally from the MMEIRS study (JICA et al., 2004), updated in 2013.

Key findings:
- **Makati:** 28 of 42 school sites situated over soil with "moderate" to "high" liquefaction potential; correlates with low Vs,30 distribution.
- **Quezon City:** Only 8 of 142 school sites situated over soil with "low" liquefaction potential.

This thesis focuses exclusively on ground-shaking hazards; liquefaction is not implicitly considered. A future liquefaction assessment is recommended for sites on Soil D and sites near flowing bodies of water (Figure A-4; PHIVOLCS, 2018).

---

## Key References

- JICA, et al. (2004): Metro Manila Earthquake Impact Reduction Study (MMEIRS)
- PEER (2013): NGA-West2 database
- UCS (2010): Universidad de Chile RENADIC archives
- NIST (2011): GCR 11-917-15 spectral matching guidance
- PHIVOLCS (2018): Philippine Institute of Volcanology and Seismology liquefaction map
- Shahi & Baker (2014): Pulse-ID algorithm
- Shiwua & Rutman (2014): Input energy parameter
