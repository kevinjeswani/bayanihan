"""Build the tidy EDP store + collapse-fragility table + authoritative index from
the 32 archetype-level PACT-style multi-stripe EDP CSV tables.

Inputs (committed source tables — author's own PERFORM-3D / SPO2IDA outputs):
  - bayanihan/data/edps/source/modelled/*.csv        (15 PERFORM-3D multi-stripe NRHA)
  - bayanihan/data/edps/source/non_modelled/*.csv    (17 SPO2IDA pseudo-EDP, same schema)

Fallback (original sandbox location, used before source tables were committed):
  - sandbox/thesis-data/Modelled/*.csv
  - sandbox/thesis-data/Non-Modelled/*.csv

Outputs (bundled — the author's own analytical outputs, committable):
  - bayanihan/data/edps/edp_store.parquet
  - bayanihan/data/edps/collapse_fragility.parquet
  - bayanihan/data/edps/index.json

Design + eq-eng rationale: docs/learnings/2026-06-26_edp_ingestion_design.md

No interpretation beyond a documented archetype-ID map (thesis file -> package ID)
and the verified storey/direction semantics. PFV/RID are stored for provenance but
are not consumed by any component fragility (see design note section 2).

Refs: Jeswani et al. 2022 (EQ Spectra, 38(3), 1946-1971); Jeswani 2021 (MASc thesis, U of T).
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

# Repo root resolved from this file's location (scripts/ is one level below root) —
# no hardcoded machine paths. The gitignored data root defaults to <repo>/sandbox and
# can be overridden with BAYANIHAN_DATA_DIR (see .env.example) for machines that keep
# the large source data elsewhere.
REPO = str(Path(__file__).resolve().parent.parent)
_DATA_DIR = os.environ.get("BAYANIHAN_DATA_DIR", os.path.join(REPO, "sandbox"))

# Prefer the committed source tables; fall back to the original sandbox location.
_COMMITTED_MODELLED = os.path.join(REPO, "bayanihan", "data", "edps", "source", "modelled")
_COMMITTED_NONMODELLED = os.path.join(REPO, "bayanihan", "data", "edps", "source", "non_modelled")
_SANDBOX_MODELLED = os.path.join(_DATA_DIR, "thesis-data", "Modelled")
_SANDBOX_NONMODELLED = os.path.join(_DATA_DIR, "thesis-data", "Non-Modelled")

MODELLED = _COMMITTED_MODELLED if os.path.isdir(_COMMITTED_MODELLED) else _SANDBOX_MODELLED
NONMODELLED = (
    _COMMITTED_NONMODELLED if os.path.isdir(_COMMITTED_NONMODELLED) else _SANDBOX_NONMODELLED
)
OUT_DIR = os.path.join(REPO, "bayanihan", "data", "edps")

GM_COLS = [f"EQ{i}" for i in range(1, 12)]

# --- file stem -> package archetype ID -------------------------------------------
# Keyed off the filename stem (NOT the Building Name label, which has at least one
# copy-paste error: S3L_C's Building Name reads "PSEUDO CHB-L"). Mirrors the ARCH_MAP
# in sandbox/build_real_inventory.py (thesis structural code -> package ID).
_FILE_PREFIX_TO_ARCH: dict[str, str] = {
    # Modelled
    "C1L_MCHC": "C1-L (Mid/Hi)",
    "C1M_HC": "C1-M (Hi)",
    "C1M_MC": "C1-M (Mid)",
    "C1M_PCLC_R1": "C1-M (Pre/Lo) FRP",   # FRP retrofit — must match BEFORE C1M_PCLC
    "C1M_PCLC": "C1-M (Pre/Lo)",
    # Non-modelled (SPO2IDA pseudo)
    "C1H_HC": "C1-H (Hi)",
    "C1L_PCLC": "C1-L (Pre/Lo)",
    "CHBL": "CHB-L",
    "CWSL": "CWS-L",
    "NL": "N-L",
    "PTC1M_HC": "PTC1-M (Hi)",
    "PTC1M_MC": "PTC1-M (Mid)",
    "S1M_HC": "S1-M (Hi)",
    "S3L": "S3-L",
    "W1L": "W-L",
}

# Order longest-prefix-first so C1M_PCLC_R1 wins over C1M_PCLC.
_PREFIXES_BY_LEN = sorted(_FILE_PREFIX_TO_ARCH, key=len, reverse=True)


def _arch_from_filename(fname: str) -> str:
    stem = fname
    for pref in _PREFIXES_BY_LEN:
        if stem.startswith(pref):
            return _FILE_PREFIX_TO_ARCH[pref]
    raise ValueError(f"No archetype mapping for file {fname!r}")


def _soilbin_from_filename(fname: str, arch_prefix_consumed: str | None = None) -> str:
    """Extract the native soil-bin token from the filename.

    Filenames look like  <PREFIX>_<BIN>_EDP-...csv  or  <PREFIX>_<BIN>_PSEUDO-EDP-...csv
    where BIN in {C1, C2, D, sC1, sC2, C}. Some have a stray extra underscore
    (e.g. CHBL_C__PSEUDO, S3L_C__PSEUDO, C1M_PCLC_R1_C1__EDP).
    """
    # Strip the trailing descriptor
    s = re.sub(r"_+(PSEUDO-)?EDP-\d{4}-\d{2}-\d{2}\.csv$", "", fname)
    # Now s = <PREFIX>_<BIN> possibly with trailing underscores
    s = s.rstrip("_")
    # The bin is the last underscore-delimited token, but for the FRP file the
    # prefix itself contains R1 (C1M_PCLC_R1_C1 -> bin C1). Match a known bin at end.
    m = re.search(r"_(sC1|sC2|C1|C2|D|C)$", s)
    if not m:
        raise ValueError(f"No soil bin found in {fname!r} (reduced to {s!r})")
    return m.group(1)


def _norm_bin(raw_bin: str) -> str:
    """Normalise the native filename bin to a canonical soil_bin.

    The 's' prefix (sC1/sC2, S1-M pseudo files) is a filename artifact for the same
    soil class as C1/C2. 'C' is the single combined soil used for SPO2IDA archetypes.
    """
    return {"sC1": "C1", "sC2": "C2"}.get(raw_bin, raw_bin)


def _read_table(path: str):
    """Parse one PACT-style EDP CSV -> (header dict, list of demand-row dicts)."""
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    hdr: dict = {}
    for r in rows[:8]:
        cells = [c.strip() for c in r]
        for i, c in enumerate(cells):
            if c.startswith("Building Name:"):
                hdr["building_name"] = c.split(":", 1)[1].strip()
            elif c == "Latitude":
                hdr["lat"] = _to_float(cells[i + 1]) if i + 1 < len(cells) else None
            elif c == "Longitude":
                hdr["lon"] = _to_float(cells[i + 1]) if i + 1 < len(cells) else None
            elif c == "Number of Stories":
                hdr["n_stories"] = int(float(cells[i + 1])) if i + 1 < len(cells) else None
            elif c == "Floor Area (sq.ft.)":
                hdr["floor_area_sqft"] = _to_float(cells[i + 1]) if i + 1 < len(cells) else None
            elif c == "Median Collapse Sa(g)":
                hdr["median_collapse_sa"] = _to_float(cells[i + 1]) if i + 1 < len(cells) else None
            elif c == "Beta Collapse":
                hdr["beta_collapse"] = _to_float(cells[i + 1]) if i + 1 < len(cells) else None

    # Locate the demand-table header row
    hi = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Intensity")

    demand_rows = []
    for r in rows[hi + 1:]:
        if not r or not r[0].strip().isdigit():
            continue
        rec = {
            "stripe": int(r[0].strip()),
            "intensity_desc": r[1].strip(),
            "mafe": _to_float(r[2]),
            "sa": _to_float(r[3]),
            "beta_m": _to_float(r[4]),
            "beta_gm": _to_float(r[5]),
            "edp_type": r[6].strip(),
            "storey": int(r[7].strip()),
            "direction": int(r[8].strip()),
        }
        for j, col in enumerate(GM_COLS):
            rec[col] = _to_float(r[9 + j]) if (9 + j) < len(r) else np.nan
        demand_rows.append(rec)

    return hdr, demand_rows


def _to_float(s):
    try:
        return float(str(s).strip())
    except (ValueError, AttributeError):
        return np.nan


# Canonical EDP-type -> short tag (Pelicun demand family for the loss-bearing ones)
_EDP_TYPE_TAG = {
    "Story Drift Ratio": "PID",
    "Building Residual Drift": "RID",
    "Acceleration": "PFA",
    "Peak Floor Velocity": "PFV",
}


def build():
    os.makedirs(OUT_DIR, exist_ok=True)

    store_records = []
    collapse_records = []
    index: dict[str, dict] = {}

    files = []
    for folder, modelled in ((MODELLED, True), (NONMODELLED, False)):
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".csv"):
                files.append((os.path.join(folder, fn), fn, modelled))

    for path, fname, modelled in files:
        arch = _arch_from_filename(fname)
        raw_bin = _soilbin_from_filename(fname)
        soil_bin = _norm_bin(raw_bin)
        hdr, demand_rows = _read_table(path)

        key = f"{arch}|{soil_bin}"

        # Collapse fragility row (one per file)
        collapse_records.append({
            "archetype": arch,
            "soil_bin": soil_bin,
            "median_collapse_sa": hdr.get("median_collapse_sa"),
            "beta_collapse": hdr.get("beta_collapse"),
            "n_stories": hdr.get("n_stories"),
            "lat": hdr.get("lat"),
            "lon": hdr.get("lon"),
            "floor_area_sqft": hdr.get("floor_area_sqft"),
            "modelled": modelled,
            "source_file": fname,
            "raw_soil_bin": raw_bin,
        })

        # Demand rows: compute per-row lognormal fit on the 11 GMs.
        for rec in demand_rows:
            gm = np.array([rec[c] for c in GM_COLS], dtype=float)
            gm_pos = gm[(gm > 0) & np.isfinite(gm)]
            if gm_pos.size >= 2:
                ln = np.log(gm_pos)
                median = float(np.exp(ln.mean()))
                beta_record = float(ln.std(ddof=1))
            elif gm_pos.size == 1:
                median = float(gm_pos[0])
                beta_record = 0.0
            else:
                median = 0.0
                beta_record = 0.0

            store_records.append({
                "archetype": arch,
                "soil_bin": soil_bin,
                "edp_type": rec["edp_type"],
                "edp_tag": _EDP_TYPE_TAG.get(rec["edp_type"], rec["edp_type"]),
                "stripe": rec["stripe"],
                "sa": rec["sa"],
                "beta_m": rec["beta_m"],
                "beta_gm": rec["beta_gm"],
                "mafe": rec["mafe"],
                "storey": rec["storey"],
                "direction": rec["direction"],
                "median": median,
                "beta_record": beta_record,
                **{c: rec[c] for c in GM_COLS},
            })

        index.setdefault(arch, {})[soil_bin] = {
            "source_file": fname,
            "n_stories": hdr.get("n_stories"),
            "modelled": modelled,
            "median_collapse_sa": hdr.get("median_collapse_sa"),
            "beta_collapse": hdr.get("beta_collapse"),
        }

    store_df = pd.DataFrame(store_records)
    collapse_df = pd.DataFrame(collapse_records)

    store_path = os.path.join(OUT_DIR, "edp_store.parquet")
    collapse_path = os.path.join(OUT_DIR, "collapse_fragility.parquet")
    index_path = os.path.join(OUT_DIR, "index.json")

    store_df.to_parquet(store_path, index=False)
    collapse_df.to_parquet(collapse_path, index=False)

    index_out = {
        "_provenance": (
            "Built by prototypes/2026-06-26_build_edp_store.py from 32 recovered "
            "PACT-style multi-stripe EDP tables (sandbox/thesis-data/{Modelled,"
            "Non-Modelled}). Author's own PERFORM-3D / SPO2IDA outputs. Keyed by "
            "package archetype ID + native soil bin. See "
            "docs/learnings/2026-06-26_edp_ingestion_design.md."
        ),
        "soil_bins": sorted(collapse_df["soil_bin"].unique().tolist()),
        "archetypes": index,
    }
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index_out, fh, indent=2, ensure_ascii=False)

    # ---- report ----
    print(f"WROTE {store_path}  ({len(store_df)} demand rows)")
    print(f"WROTE {collapse_path}  ({len(collapse_df)} archetype×soil collapse rows)")
    print(f"WROTE {index_path}")
    print(f"\nfiles parsed: {len(files)} (expect 32)")
    print(f"distinct (archetype, soil_bin): {len(collapse_df)}")
    print(f"distinct archetypes: {collapse_df['archetype'].nunique()}")
    print(f"soil bins: {index_out['soil_bins']}")
    print("\ncollapse fragility per archetype×soil:")
    for _, r in collapse_df.sort_values(["archetype", "soil_bin"]).iterrows():
        print(f"   {r['archetype']:20s} {r['soil_bin']:4s}  "
              f"Sa_col={r['median_collapse_sa']:.3f}  beta={r['beta_collapse']:.3f}  "
              f"N={r['n_stories']}  {'mod' if r['modelled'] else 'pseudo'}")

    # Sanity: every collapse Sa present, beta in (0,1], n_stories>=1
    assert collapse_df["median_collapse_sa"].notna().all(), "missing collapse Sa"
    assert collapse_df["beta_collapse"].between(0, 1.0).all(), "collapse beta out of range"
    assert (collapse_df["n_stories"] >= 1).all(), "bad story count"
    # Sanity: BetaGM all zero (GM dispersion is in the empirical sample, see design note §3)
    assert (store_df["beta_gm"].fillna(0) == 0).all(), "unexpected nonzero BetaGM"
    print("\nsanity checks: PASS")


if __name__ == "__main__":
    build()
