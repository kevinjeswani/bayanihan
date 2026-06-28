"""Generate a synthetic demo school inventory for bayanihan.

This script produces ~50 hypothetical Manila school buildings for use in
examples and CI.  It is NOT real building data.  All identifiers are generic
(SCH_001, SCH_002, …) and coordinates are jittered within city bounding boxes.

Archetype and construction-era distributions are calibrated to match the
real portfolio proportions documented in:
  Jeswani, K. K. (2021). The Seismic Resilience of Critical
  Spatially-Distributed Building Portfolios. MASc thesis, U of T.
  (Chapter 4 inventory characteristics — see docs/thesis/data/inventory_characteristics.yaml)
  Jeswani et al. (2022). Earthquake Spectra, 38(3), 1946-1971.
  https://doi.org/10.1177/87552930221086304

Run:
    uv run python utils/gen_synthetic_inventory.py

Output:
    bayanihan/data/inventory/manila_schools_demo.geojson

Seed: 2021 (thesis year) — fully reproducible.
"""

from __future__ import annotations

import math
import pathlib
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "bayanihan" / "data" / "inventory" / "manila_schools_demo.geojson"

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 2021
RNG = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# Portfolio parameters derived from inventory_characteristics.yaml
# ---------------------------------------------------------------------------

# City split: Makati=96, QC=925 → 96/1021 ≈ 9.4% Makati, 90.6% QC
# With 50 buildings: ~5 Makati, ~45 QC
N_TOTAL = 50
N_MAKATI = 5
N_QC = N_TOTAL - N_MAKATI

# ---------------------------------------------------------------------------
# Geographic bounding boxes (approximate city envelopes)
# ---------------------------------------------------------------------------
# Makati CBD + school district (~26 km²)
MAKATI_BBOX = {
    "lat_min": 14.545,
    "lat_max": 14.570,
    "lon_min": 121.010,
    "lon_max": 121.040,
}

# Quezon City (~165 km²)
QC_BBOX = {
    "lat_min": 14.610,
    "lat_max": 14.720,
    "lon_min": 121.020,
    "lon_max": 121.110,
}

# ---------------------------------------------------------------------------
# Archetype catalogue
# 20 valid archetype IDs (YAML keys).
# ---------------------------------------------------------------------------
VALID_ARCHETYPE_IDS: list[str] = [
    # NRHA-modelled
    "C1-L (Mid/Hi)",
    "C1-M (Hi)",
    "C1-M (Mid)",
    "C1-M (Pre/Lo)",
    "C1-M (Pre/Lo) FRP",
    # EDP-proxy
    "PTC1-M (Mid)",
    "PTC1-M (Hi)",
    # Primary-Simplified
    "C1-L (Pre/Lo)",
    "C1-H (Hi)",
    "S1-M (Hi)",
    # Secondary-Simplified
    "CWS-L",
    "S3-L",
    "CHB-L",
    "W-L",
    "N-L",
    # Merged
    "PC-L",
    "PTC1-M (Pre/Lo)",
    "PTC4-M (Lo)",
    "C4-L (Lo/Mid)",
    "C4-M (Mid)",
]
assert len(VALID_ARCHETYPE_IDS) == 20

# ---------------------------------------------------------------------------
# Archetype properties (stories, year_built range, replacement cost)
# ---------------------------------------------------------------------------
# replacement_cost_php_per_m2: median from thesis contract cost data or
# illustrative estimate (flagged with * in notes below).
# story counts: canonical value from archetypes.yaml.
# year_built_range: maps to code era.
#
# Replacement cost data source:
#   QC concrete median ₱19,800/m² (Table 4-5, thesis p.54) → used for RC archetypes
#   QC steel median ₱30,500/m² (Table 4-5, thesis p.54) → used for steel archetypes
#   Older / non-concrete buildings: illustrative ₱12,000/m² (*illustrative*)
#   Note: per-m² costs multiplied by approximate floor areas from archetypes.yaml Table 5-5
#
# All replacement_cost_php values are SYNTHETIC ILLUSTRATIVE ESTIMATES.
# Do not cite as actual replacement cost data.

ARCHETYPE_PROPS: dict[str, dict[str, Any]] = {
    "C1-L (Mid/Hi)": {
        "stories": 2,
        "year_built_range": (1994, 2018),  # Mid/Hi code: 1994+
        "floor_area_m2": 597,  # 6-classroom: ~31.5x9.5x2
        "cost_per_m2": 19_800,
        "site_class_options": ["SC", "SD"],
    },
    "C1-M (Hi)": {
        "stories": 4,
        "year_built_range": (2004, 2018),  # High code: 2004+
        "floor_area_m2": 1026,  # ~27x9.5x4
        "cost_per_m2": 19_800,
        "site_class_options": ["SC", "SD"],
    },
    "C1-M (Mid)": {
        "stories": 3,
        "year_built_range": (1995, 2003),  # Mid code: 1995-2003
        "floor_area_m2": 918,  # ~33x9.25x3
        "cost_per_m2": 19_800,
        "site_class_options": ["SC", "SD"],
    },
    "C1-M (Pre/Lo)": {
        "stories": 3,
        "year_built_range": (1950, 1994),  # Pre/Lo: pre-1975 to 1994
        "floor_area_m2": 918,
        "cost_per_m2": 19_800,
        "site_class_options": ["SC", "SD"],
    },
    "C1-M (Pre/Lo) FRP": {
        "stories": 3,
        "year_built_range": (1950, 1994),  # same as Pre/Lo (retrofitted)
        "floor_area_m2": 918,
        "cost_per_m2": 22_000,  # *illustrative* – retrofit cost premium applied
        "site_class_options": ["SC", "SD"],
    },
    "PTC1-M (Mid)": {
        "stories": 5,
        "year_built_range": (1994, 2002),  # Mid code: 1994-2002 start
        "floor_area_m2": 1_080,  # Table 6-5 thesis
        "cost_per_m2": 19_800,
        "site_class_options": ["SC"],  # Makati typically Soil C
    },
    "PTC1-M (Hi)": {
        "stories": 5,
        "year_built_range": (2003, 2018),  # High code: 2003+ start
        "floor_area_m2": 2_737,  # Table 6-5 thesis
        "cost_per_m2": 19_800,
        "site_class_options": ["SC"],
    },
    "C1-L (Pre/Lo)": {
        "stories": 2,
        "year_built_range": (1945, 1994),  # Pre/Lo
        "floor_area_m2": 599,  # Table 5-5
        "cost_per_m2": 12_000,  # *illustrative* older building
        "site_class_options": ["SC", "SD"],
    },
    "C1-H (Hi)": {
        "stories": 10,
        "year_built_range": (2004, 2018),  # High code: 2004+
        "floor_area_m2": 17_577,  # Table 5-5
        "cost_per_m2": 19_800,
        "site_class_options": ["SC"],  # Makati only; Soil C
    },
    "S1-M (Hi)": {
        "stories": 4,
        "year_built_range": (2004, 2018),  # High code
        "floor_area_m2": 2_783,  # Table 5-5
        "cost_per_m2": 30_500,  # QC steel median
        "site_class_options": ["SC", "SD"],
    },
    "CWS-L": {
        "stories": 2,
        "year_built_range": (1945, 1974),  # Pre-code semi-concrete
        "floor_area_m2": 600,
        "cost_per_m2": 12_000,  # *illustrative*
        "site_class_options": ["SC", "SD"],
    },
    "S3-L": {
        "stories": 1,
        "year_built_range": (1970, 1994),  # Pre/Lo code
        "floor_area_m2": 110,  # Table 5-5
        "cost_per_m2": 30_500,  # light steel
        "site_class_options": ["SC", "SD"],
    },
    "CHB-L": {
        "stories": 1,
        "year_built_range": (1945, 1980),  # Pre/Lo
        "floor_area_m2": 100,  # Table 5-5
        "cost_per_m2": 12_000,  # *illustrative*
        "site_class_options": ["SC", "SD"],
    },
    "W-L": {
        "stories": 1,
        "year_built_range": (1900, 1974),  # Pre-code Gabaldon/wood
        "floor_area_m2": 369,  # Table 5-5
        "cost_per_m2": 8_000,  # *illustrative* wood construction
        "site_class_options": ["SC", "SD"],
    },
    "N-L": {
        "stories": 1,
        "year_built_range": (1945, 1974),  # Pre-code makeshift
        "floor_area_m2": 145,  # Table 5-5
        "cost_per_m2": 6_000,  # *illustrative* non-engineered
        "site_class_options": ["SC", "SD"],
    },
    "PC-L": {
        "stories": 1,
        "year_built_range": (1975, 1994),  # Lo code
        "floor_area_m2": 200,  # *illustrative* precast
        "cost_per_m2": 15_000,  # *illustrative*
        "site_class_options": ["SC", "SD"],
    },
    "PTC1-M (Pre/Lo)": {
        "stories": 3,
        "year_built_range": (1974, 1994),  # Pre/Lo Makati PTMRF
        "floor_area_m2": 918,
        "cost_per_m2": 19_800,
        "site_class_options": ["SC"],  # Makati
    },
    "PTC4-M (Lo)": {
        "stories": 4,
        "year_built_range": (1975, 1993),  # Lo code
        "floor_area_m2": 1_200,  # *illustrative* PTMRF + RCSW
        "cost_per_m2": 19_800,
        "site_class_options": ["SC"],  # Makati
    },
    "C4-L (Lo/Mid)": {
        "stories": 2,
        "year_built_range": (1975, 2003),  # Lo/Mid code
        "floor_area_m2": 597,
        "cost_per_m2": 19_800,
        "site_class_options": ["SC", "SD"],
    },
    "C4-M (Mid)": {
        "stories": 3,
        "year_built_range": (1995, 2003),  # Mid code
        "floor_area_m2": 918,
        "cost_per_m2": 19_800,
        "site_class_options": ["SC", "SD"],
    },
}

# Confirm we haven't missed any archetype
assert set(ARCHETYPE_PROPS.keys()) == set(VALID_ARCHETYPE_IDS), (
    f"Mismatch: {set(VALID_ARCHETYPE_IDS) - set(ARCHETYPE_PROPS.keys())}"
)

# ---------------------------------------------------------------------------
# Archetype sampling distributions
# ---------------------------------------------------------------------------
# Makati distribution (by building count, calibrated from Figure 4-11 floor area
# shares but normalised to count since floor area skews toward large PTC1-M).
# The dominant archetypes are PTC1-M (Mid) + PTC1-M (Hi) = ~57% floor area.
# High-rise C1-H (Hi) = 2 buildings but large floor area.
# We use count-based proportions consistent with thesis narrative.

MAKATI_ARCHETYPES = [
    "C1-L (Pre/Lo)",      # Low-rise Pre/Lo RCMRF: ~1% floor area, older stock
    "C1-L (Mid/Hi)",      # Low-rise Mid/Hi RCMRF: ~0.3% floor area
    "C1-M (Pre/Lo)",      # Mid-rise Pre/Lo RCMRF: ~14% floor area
    "PTC1-M (Pre/Lo)",    # Mid-rise Pre/Lo PTMRF: ~6% floor area (merged)
    "PTC4-M (Lo)",        # Mid-rise Lo PTMRF+SW: ~1% (1 building)
    "PTC1-M (Mid)",       # Mid-rise Mid PTMRF: ~32% floor area — dominant
    "PTC1-M (Hi)",        # Mid-rise Hi PTMRF: ~25% floor area
    "C4-L (Lo/Mid)",      # Low-rise Lo/Mid RCMRF+SW: ~0.4%
    "C1-H (Hi)",          # High-rise Hi RCMRF: ~18% floor area, 2 buildings
    "C1-M (Pre/Lo) FRP",  # FRP retrofit subset of Pre/Lo
]
MAKATI_WEIGHTS = [
    2,   # C1-L (Pre/Lo): rare in Makati
    1,   # C1-L (Mid/Hi)
    7,   # C1-M (Pre/Lo): significant count
    3,   # PTC1-M (Pre/Lo)
    1,   # PTC4-M (Lo): 1 building
    15,  # PTC1-M (Mid): most dominant
    12,  # PTC1-M (Hi)
    1,   # C4-L (Lo/Mid)
    2,   # C1-H (Hi): 2 buildings but outsized floor area
    1,   # C1-M (Pre/Lo) FRP: retrofit variant
]

# Quezon City distribution (by building count from Table 4-7 narrative + Figure 4-13)
# C1-M (Hi) + S1-M (Hi) ≈ 47% of QC building count (text §4.4.5)
# QC RCMRF total ~73%; remainder split across older/secondary types
QC_ARCHETYPES = [
    "C1-L (Pre/Lo)",   # 2-storey pre/lo RCMRF
    "C1-L (Mid/Hi)",   # 2-storey mid/hi RCMRF
    "C1-M (Pre/Lo)",   # 3-4 storey pre/lo RCMRF
    "C1-M (Mid)",      # 3-4 storey mid RCMRF
    "C1-M (Hi)",       # 3-4 storey hi RCMRF — most numerous
    "S1-M (Hi)",       # 4-storey steel MRF hi
    "C4-L (Lo/Mid)",   # 2-storey RCMRF+SW
    "C4-M (Mid)",      # 3-4 storey RCMRF+SW
    "CWS-L",           # semi-concrete/wood
    "S3-L",            # prefab light steel
    "CHB-L",           # CHB masonry
    "W-L",             # Gabaldon/wood
    "N-L",             # makeshift
    "PC-L",            # precast (rare, excluded from portfolio but exists in stock)
]
QC_WEIGHTS = [
    6,   # C1-L (Pre/Lo)
    8,   # C1-L (Mid/Hi)
    5,   # C1-M (Pre/Lo)
    9,   # C1-M (Mid)
    20,  # C1-M (Hi): most common single archetype in QC
    8,   # S1-M (Hi): ~14% by count combined with C1-M Hi = 47%
    2,   # C4-L (Lo/Mid)
    3,   # C4-M (Mid)
    3,   # CWS-L
    2,   # S3-L
    2,   # CHB-L
    1,   # W-L
    1,   # N-L
    1,   # PC-L
]


def _normalise(weights: list[int]) -> list[float]:
    total = sum(weights)
    return [w / total for w in weights]


def _sample_archetype(archetypes: list[str], weights: list[int], n: int) -> list[str]:
    probs = _normalise(weights)
    return list(RNG.choice(archetypes, size=n, p=probs))


def _sample_coords(bbox: dict[str, float], n: int) -> list[tuple[float, float]]:
    """Sample (lat, lon) uniformly within a bounding box."""
    lats = RNG.uniform(bbox["lat_min"], bbox["lat_max"], n)
    lons = RNG.uniform(bbox["lon_min"], bbox["lon_max"], n)
    return list(zip(lats, lons))


def _sample_year(archetype_id: str) -> int:
    lo, hi = ARCHETYPE_PROPS[archetype_id]["year_built_range"]
    return int(RNG.integers(lo, hi + 1))


def _sample_site_class(archetype_id: str) -> str:
    opts = ARCHETYPE_PROPS[archetype_id]["site_class_options"]
    return str(RNG.choice(opts))


def _replacement_cost(archetype_id: str) -> int:
    props = ARCHETYPE_PROPS[archetype_id]
    area = props["floor_area_m2"]
    cost_per_m2 = props["cost_per_m2"]
    # Add ±20% jitter (lognormal dispersion β≈0.2 consistent with thesis)
    jitter = float(RNG.lognormal(mean=0.0, sigma=0.20))
    total = math.floor(area * cost_per_m2 * jitter / 1_000) * 1_000
    return max(total, 100_000)


def generate(output_path: pathlib.Path = OUTPUT_PATH, seed: int = SEED) -> gpd.GeoDataFrame:
    """Generate the synthetic inventory and write to GeoJSON.

    Re-seeds the module RNG at the start so every call is reproducible from the
    same seed. (The module-level RNG is otherwise consumed across calls, so a
    second call in the same process would diverge from the first.)

    Returns the GeoDataFrame.
    """
    global RNG
    RNG = np.random.default_rng(seed)

    # --- Sample archetypes per city ---
    mkt_archetypes = _sample_archetype(MAKATI_ARCHETYPES, MAKATI_WEIGHTS, N_MAKATI)
    qc_archetypes = _sample_archetype(QC_ARCHETYPES, QC_WEIGHTS, N_QC)

    # --- Sample coordinates ---
    mkt_coords = _sample_coords(MAKATI_BBOX, N_MAKATI)
    qc_coords = _sample_coords(QC_BBOX, N_QC)

    # --- Build rows ---
    rows: list[dict[str, Any]] = []
    idx = 1

    for archetype_id, (lat, lon) in zip(mkt_archetypes, mkt_coords):
        props = ARCHETYPE_PROPS[archetype_id]
        rows.append(
            {
                "id": f"SCH_{idx:03d}",
                "archetype_id": archetype_id,
                "city": "Makati",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "stories": int(props["stories"]),
                "year_built": _sample_year(archetype_id),
                "site_class": _sample_site_class(archetype_id),
                "replacement_cost_php": _replacement_cost(archetype_id),
                "geometry": Point(lon, lat),
            }
        )
        idx += 1

    for archetype_id, (lat, lon) in zip(qc_archetypes, qc_coords):
        props = ARCHETYPE_PROPS[archetype_id]
        rows.append(
            {
                "id": f"SCH_{idx:03d}",
                "archetype_id": archetype_id,
                "city": "Quezon City",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "stories": int(props["stories"]),
                "year_built": _sample_year(archetype_id),
                "site_class": _sample_site_class(archetype_id),
                "replacement_cost_php": _replacement_cost(archetype_id),
                "geometry": Point(lon, lat),
            }
        )
        idx += 1

    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    # Drop lat/lon columns that are now redundant with geometry
    # (keep them as convenience attributes for non-GIS downstream use)
    col_order = [
        "id",
        "archetype_id",
        "city",
        "lat",
        "lon",
        "stories",
        "year_built",
        "site_class",
        "replacement_cost_php",
        "geometry",
    ]
    gdf = gdf[col_order]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")
    print(f"Written {len(gdf)} buildings → {output_path}")
    print(f"  Makati: {(gdf.city == 'Makati').sum()}  |  Quezon City: {(gdf.city == 'Quezon City').sum()}")
    print(f"  Archetypes represented: {gdf.archetype_id.nunique()} of {len(VALID_ARCHETYPE_IDS)}")
    print(f"  Archetype distribution:\n{gdf.archetype_id.value_counts().to_string()}")
    return gdf


if __name__ == "__main__":
    generate()
