# Chapter 3: Seismic Hazard Definition
*Thesis: Jeswani, K.K. (2021). The Seismic Resilience of Critical Spatially-Distributed Building Portfolios. MASc Thesis, University of Toronto.*
*Printed pages 19–35 (PDF pages 46–62).*

---

## 3.0 Overview

Chapter 3 describes active fault sources surrounding Metro Manila used in Chapter 7 to guide a ground-motion selection procedure for nonlinear time history analyses (NRHA). Outputs from the latest Philippine probabilistic seismic hazard analysis (PSHA), PEM2020 (Peñarubia et al., 2020), are used to define seismic hazard at each school site across a range of intensities, modified for local site conditions and near-fault directivity effects. Appropriate ground-motion records are selected from global sources and scaled using bidirectional spectral matching. The overall process is illustrated in Figure 3-1.

*Personal communications with subject matter experts are summarized in Table P-2 (Preface) and Table R-2 (References).*

---

## 3.1 Overview of Seismic Hazards in Metro Manila
*(Printed page 20)*

The latest Philippine PSHA, **PEM2020** (Peñarubia et al., 2020), identifies the **West Valley Fault (WVF)** — dividing eastern Makati and Quezon City — as the most significant seismic threat. At the design-level hazard (10% PoE in 50 years, **475-year return period**), the largest contributions come from **shallow crustal faults within 25 km** capable of moment magnitude (**Mw**) **6.5 to 7.75** events.

A second cluster of non-zero PoE at distances of **100–150 km** is also present in the disaggregation, attributed to:
- Interface and intraslab events in the **Manila Trench** (west of Metro Manila) subduction zone
- East Luzon Trough / Philippine Trench (east of Metro Manila) interface events (less likely)

Additional earthquake scenarios from the MMEIRS study (JICA et al., 2004) — based on historical earthquake review — include (Appendix A.1):
- **East Valley Fault (EVF)** — subparallel to WVF
- Segments of the 1,250-km **Philippine Fault System (PFS)**
- East Luzon Trough and Transform Fault
- East Zambales Fault
- Lubang Fault
- Central Mindoro Fault
- Laguna-Banahaw Fault
- Casiguran Fault
- 1863 Manila Bay Earthquake (no identified source fault)

Fault traces are compiled from PHIVOLCS in the Global Earthquake Model (GEM, 2020a) Global Active Fault (GAF) database, supplemented by two additional MMEIRS scenarios (Laguna-Banahaw Fault, 1863 Manila Bay Earthquake). USGS (2018) subduction slab geometries (Slab2) for the Manila Trench and East Luzon Trough/Philippine Trench are also presented with slab depth contours. Peñarubia et al. (2020) also note the **General Nakar West (GNW)** and **General Nakar East** faults as the closest faults near Metro Manila aside from the EVF and WVF.

*Figure 3-2: Seismic generators for Metro Manila (after GEM 2020a, USGS 2018, JICA et al. 2004; boundaries: PhilGIS 2011)*

---

### 3.1.1 Defining the Seismic Hazard for School Sites
*(Printed page 22)*

The target intensity range for the Makati and Quezon City public-school building portfolios is defined across five levels (Table 3-1):

**Table 3-1: Selected range of seismic intensities for Metro Manila**

| Intensity Level | Return Period TR [years] | PoE in 50 Years [%] | MAFE |
|---|---|---|---|
| Frequent (SLE) | 75 | 63% | 0.01250 |
| Probable | 175 | 30% | 0.00523 |
| Design-Level (DBE) | 475 | 10% | 0.00210 |
| Rare | 975 | 5% | 0.00103 |
| Very Rare (MCE) | 2,475 | 2% | 0.00040 |

Based on a review of existing PSHAs (Wong, Dawson & Dober, 2009; Peñarubia et al., 2020; Dungca & Chua, 2016):
- **475- to 2,475-year** events are expected to be governed by **near-fault shallow crustal** events along the WVF and EVF.
- **More frequent events** (lower return periods): far-fault shallow crustal events from segments of the PFS, GNW, Lubang Faults, and/or interface events along the Manila Trench; subduction intraslab events are also expected to produce low-intensity ground shaking.
- Ground-motion selection in this study is restricted to **shallow crustal and subduction interface**; intraslab events are noted as a direction for future work.

Mean spectral acceleration (Sa) values across multiple periods **T = {0, 0.2, 0.5, 0.8, 1, 2 s}** and across all five intensity levels were provided by GEM (2019b) from the latest **Philippine Earthquake Model (PEM2020)** developed in the OpenQuake (GEM, 2020b) platform. The hazard curve for Makati and Quezon City school sites is presented in Figure 3-3 (in terms of MAFE vs. PGA).

All PEM2020 values correspond to:
- Reference site: **Vs,30 = 760 m/s**
- Horizontal component: **geomean (average horizontal)**

An example spatial distribution (2,475-year Sa at T = 0.8 s) is shown in Figure 3-4.

---

### 3.1.2 Site-Class (Soil) Model
*(Printed page 25)*

**Vs,30** provides estimation of site response (amplification) and is strongly related to geomorphological zone and liquefaction potential.

The site model adopted is the **Greater Metro Manila Area (GMMA) hybrid soil model** from **Allen et al. (2014)**:
- Takes the **mean Vs,30** between topographic gradient-based and borehole-based (SPT-N) methods at **263 points** across GMMA.
- Supplemented by Vs,30 values at an additional **32 sites** from **Grutas & Yamanaka (2012)** via microtremor array measurements.

Vs,30 values at each school campus are spatially interpolated using **inverse distance weighted (IDW)** method (ESRI, 2019), illustrated in Figure 3-5.

**Result — school campus site classification:**
- **152 campus sites on Soil C** (Vs,30 = 360–760 m/s)
- **32 campus sites on Soil D** (Vs,30 = 180–360 m/s)

*Figure 3-5: 2017 Philippine Earthquake Model — Metro Manila site class model and school locations; After PHIVOLCS (2017)*

---

### 3.1.3 Target Spectrum and Site Amplification
*(Printed page 27)*

Sites are grouped by soil class. The **PEM2020** uses the following GMPEs to account for median GM amplitudes for shallow crustal faults:
- **Chiou & Youngs (2008), CY08**
- **Boore & Atkinson (2008), BA08**

As BA08 uses the same reference Vs,30 = 760 m/s as the Sa values from GEM, **BA08 period-dependent site amplification factors** corresponding to the Vs,30 at each site were applied to the **target geomean Sa curves**.

Results are shown in Figure 3-6:
- (a) & (c): Median 75- to 2,475-year Sa on reference Vs,30 = 760 m/s
- (b) & (d): Sa with BA08 site amplification factors applied

---

## 3.2 Ground-Motion Definition for Non-Linear Response History Analysis
*(Printed page 28)*

---

### 3.2.1 General Concerns for Near-Fault Ground Motion Selection
*(Printed page 28)*

**NIST (2011) guidelines (GCR 11-917-15)** were followed for seismic hazard definition and GM selection, due to lack of in-depth recommendations in the National Structural Code of the Philippines (NSCP, ASEP 2016).

Key considerations:
- The design spectrum for sites within **15–20 km of an active fault** should be adjusted upward for **average directivity effects**.
- Forward-directivity, backward-directivity, and other near-fault phenomena cause significant **velocity pulses** in GM time-histories (pulse-like motions).
- Limited Philippine strong-motion data recordings exist (Peñarubia et al., 2020).

Initial approach:
- Preliminary seed pulse-like GMs selected from the PEER (2013) shallow crustal earthquake database.
- GMs amplitude-scaled to the target 2,475-year geomean Sa curves (per NSCP (ASEP 2016) and ASCE-7 (2010) recommendations).
- Result: **Excessive scaling factors** because record-suite mean Sa did not match the shape of the target Sa (even accounting for average directivity). Problem was exacerbated when scaling down to lower intensities. NRHAs with amplitude-scaled suites produced numerous collapses at the 2,475-year TR.

**Solution adopted**: Bidirectional time-domain **spectral matching** method by **So et al. (2015)**, to condition GMs on a given intensity level while considering fit of the suite mean to the target spectrum.

---

### 3.2.2 Consideration for Average Directivity Amplification
*(Printed page 28)*

The **Shahi & Baker (2013) (SB13)** model for **average directivity amplification**, μ(Sa|M, R, T), for **vertical strike-slip (SS)** ruptures was used.

Model inputs: magnitude (M), closest source-to-site distance (R = Rjb = Rrup for vertical SS faults), and structural period (T). The model computes the conditional average amplification considering:
- Probability of directivity
- Lengths (s) of fault striking toward the site
- Hypocenter-site angle (θ)
- Resulting pulse period (Tp)

Application:
- μ(Sa|M, R, T) was calculated for each school site at distances from the WVF (R), across the range of structural periods (T), and for magnitudes **M = {6.2, 6.5, 7.0, 7.2, 7.5}** corresponding to the five intensity levels.
- M values approximated from the WVF magnitude-frequency distribution (MFD) described by Peñarubia et al. (2020) and PHIVOLCS (2017).

Results (Figure 3-7):
- Amplification distribution shifts toward **longer periods** with increasing magnitude.
- Average directivity amplification effects are **fairly low (2–7% increase)** for low- and mid-rise structures in the portfolio.

---

### 3.2.3 Defining Target "Maximum" and "Minimum" Direction Spectra
*(Printed page 29)*

Per NIST (2011), GM records input to structural models should be oriented consistent with **strike-normal and strike-parallel** for near-fault sites.

The bidirectional time-domain spectral matching script **RspMatchBi** by **Grant (2011; 2019)** was employed. Input target spectra required for spectral matching define major- and minor-axis Sa demand, referred to as:
- **TSa,max** — target maximum-direction spectrum
- **TSa,min** — target minimum-direction spectrum

Approach (using Boore, 2010):
- **Sa,RotD0** (0th percentile) — minimum direction
- **Sa,RotD50** (50th percentile / geomean) — median direction
- **Sa,RotD100** (100th percentile) — maximum direction

Conversions:
1. **TSa,max**: Geomean target spectral values (from §3.2.2) are converted to the target maximum-direction spectrum using the **Shahi & Baker (2013) Sa,RotD100/Sa,RotD50 ratios** ranging from **1.19 at T = 0.01 s** to **1.29 at T = 10 s**.
2. **TSa,min**: Defined by Grant (2011) using mean Sa,RotD0/Sa,RotD100 values (ranging from **0.717 at T = 0.1 s** to **0.600 at T = 3 s**) proposed by **Hong & Goda (2007)**, defined as orthogonal to the maximum response.

The TSa,min spectra for this study correspond to the Sa,RotD0 of GM records.

*Figure 3-8: Target maximum and minimum direction 2,475-year (median) TSa for Soil D and Soil C site groups*

---

### 3.2.4 Ground-Motion Record Selection for NRHA
*(Printed page 31)*

GM selection and spectral matching procedure is summarized in Figure 3-9.

Based on So et al. (2015) and Pokhrel et al. (2014), **80–93% of 2,475-year GM suites should be composed of pulse-like motions** (determined from disaggregation of private/internal PSHAs for Metro Manila at periods of interest 0.3–0.6 s).

Records selected:
- **9 pulse-like + 1 non-pulse seed shallow crustal GM records** from the **NGA-West2 database (PEER, 2013)** using the 2,475-year TSa,max (RotD100).
- **1 subduction GM record pair** (per Soil C and per Soil D) from the **2010 Maule, Chile Earthquake** using the Universidad de Chile RENADIC archives (UCS, 2010).

Notes:
- Subcrustal (intraslab) GMs from the Manila Trench were omitted; noted for future study.
- Selection procedure and list of selected GMs: Appendix A.2.
- Records baseline-corrected in **SeismoSignal (SeismoSoft, 2016)** as necessary.
- MATLAB script **RotDSpectro (Kong, 2016)** provided by Thangappa (2019a; 2019b) used to calculate Sa,RotD100, Sa,RotD50, and Sa,RotD0.

---

### 3.2.5 Spectral Matching
*(Printed page 32)*

Procedure: adapted from **Grant (2012)** and **Almufti et al. (2015)** to preserve velocity pulses during spectral matching, for each intensity level and each site group.

Pulse handling:
1. **Shahi & Baker (2014) pulse-ID algorithm** used to identify velocity pulses in orthogonal GM record pairs.
2. Velocity pulses extracted from each record pair.
3. Residual (no-pulse) records rotated and spectrally matched to target spectra (§3.2.3).
4. Velocity pulse added back to the spectrally-matched record pairs.
5. Process illustrated in Figure 3-10; details in Appendix A.3.1.

Verification:
- Directional spectra of matched records (Sa,RotD100,SM, Sa,RotD50,SM, Sa,RotD0,SM) compared against corresponding target spectra (TSa,max, TSa,med, TSa,min) at each intensity and soil group.
- Figure 3-11: Soil D RotD50 Sa — (a) 2,475-yr max/median/min TSa, SM suite mean and individual records; (b) 75- to 2,475-yr spectral matching.
- Detailed comparison in Appendix A.3.2; detailed target spectra and spectral matching results in Appendix A.3.3.

**Important note on hybrid soil model revision**: A change to the hybrid soil model (§3.1.2) was made in later research stages for the portfolio analysis (Chapter 7). Target spectra definitions were updated without re-running spectral matching on GM suites. A better match between initial targets and suite means was achieved in earlier project iterations. This did not significantly impact vulnerability derivations (Chapter 6), which use spectrally-matched suite mean Sa as intensity measures. The portfolio analysis (Chapter 7) is not expected to be significantly impacted if spectral matching were updated.

---

## 3.3 Concluding Remarks
*(Printed page 35)*

Chapter 3 introduces the faults governing Metro Manila seismicity (central to rupture scenario generation in Chapter 7). Ground-motion suites were selected to represent the governing **near-fault hazard**, consisting primarily of **pulse-like motions**. Suites were scaled and spectrally matched to target spectra of the defined seismic intensities for use with the nonlinear models described in Chapter 5.

---

## Cross-References
- Table 7-2 (printed p. 158): Fault rupture distance parameter summary — WVF (Mw 6.5, 7.3, Rjb = 0–9.5 km), EVF (Mw 6.9, Rjb = 2.9–20.0 km), GNW (Mw 7.6), Manila Trench (Mw 7.9).
- Table 7-3 (printed p. 158): Full GMPE logic-tree weights adopted from PEM2020 — 4 GMPEs per tectonic regime (shallow crustal + subduction interface), each weighted 0.25.
- Section 7.1 / Figure 3-9: Rupture scenario selection for portfolio loss estimation.
- Appendix A.1: Historical earthquake scenario list (MMEIRS).
- Appendix A.2: Ground-motion record selection details and record list.
- Appendix A.3.1–A.3.3: Spectral matching procedure, results, and target spectra.
