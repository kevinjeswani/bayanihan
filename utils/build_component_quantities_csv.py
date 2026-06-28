"""Generate the packaged per-archetype FEMA P-58 component-quantity table.

Reads ``docs/thesis/data/component_quantities.yaml`` (the P3 extraction of thesis
Table D-13, printed p.311) and emits
``bayanihan/data/component_quantities.csv`` — a long-format, package-
loadable table that ``building._build_cmp_marginals`` consumes to populate each
archetype's Pelicun component model with the REAL thesis component population
instead of the 5-component ``_DEFAULT_CMP_INVENTORY`` placeholder.

SOURCE RECONCILIATION (2026-06-26)
----------------------------------
The recovered author workbook
``sandbox/thesis-data/Seismic Resilience of MM Schools - EDP Manager - KJ - 2020-10-18.xlsx``
was audited as the candidate "authoritative" source. Its per-archetype sheets
(C1-M(HC), CHB, ...) hold the EDP derivations (drift/PFA/PFV per intensity) that
were fed to PACT, and ``P58Simp`` holds FEMA P-58 Vol-1 Table 5-4/5-5 EDP-dispersion
correction factors — NOT component populations. ``BldgSpec_Inp`` / ``AllVulnPlots``
hold archetype-level replacement cost/time/peak-population and 2021 Thesis plot-category
maps. None of these tabulate FEMA P-58 component COUNTS per component ID; those were
entered directly into the proprietary platform used in the 2021 Thesis. Therefore the authoritative, citable
source for per-archetype component quantities remains **thesis Table D-13**, already
captured at high confidence in ``component_quantities.yaml``. The workbook corroborates
the 14-archetype roster, structural systems, and replacement costs (no conflict found).

COLUMN -> PH.* FRAGILITY-ID MAPPING
-----------------------------------
Table D-13 records quantities under generic component columns (bc_1s, chb_solid, ...).
The PH.* fragility ID for each column depends on the archetype's structural system and
the thesis fragility-basis assignments (Table 6-2, §6.2.2; ductile/non-ductile lists
§6.2.4 p.~225-226; CHB reinforcement §6.3.1). Mapping rules below; every emitted ID
resolves in both ``fragility.csv`` and ``consequence_repair.csv``.

PROVENANCE
----------
Every row carries ``thesis_source`` (Table D-13 + the mapping basis) and
``provenance_confidence``. Items the thesis does not pin precisely (FRP retrofit
structural component; CWS-L story-2 light frame) are flagged ``medium`` for Kevin.

Refs: Jeswani et al. 2022 (EQ Spectra, 38(3), 1946-1971); Jeswani 2021 (MASc thesis, U of T).
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
YAML_PATH = REPO / "docs" / "thesis" / "data" / "component_quantities.yaml"
OUT_CSV = REPO / "bayanihan" / "data" / "component_quantities.csv"

# ---------------------------------------------------------------------------
# Structural beam-column system per archetype (Table 6-2 fragility basis;
# ductile/non-ductile lists §6.2.4 printed p.225-226; PT §6.2.2; steel S1/S3).
#   "DRCMRF"  -> ductile RC moment frame
#   "NDRCMRF" -> non-ductile RC moment frame
#   "PTRCMRF" -> post-tensioned RC moment frame (same fragility as ductile; PT costs)
#   "SMRF"    -> steel moment frame
#   None      -> no engineered beam-column frame (bc quantities are 0 in D-13)
# ---------------------------------------------------------------------------
STRUCT_SYSTEM: dict[str, str | None] = {
    "C1-M (Hi)": "DRCMRF",
    "C1-M (Mid)": "DRCMRF",
    "C1-M (Pre/Lo)": "NDRCMRF",
    "C1-M (Pre/Lo) FRP": "DRCMRF",   # FRP retrofit -> ductile detailing (§5.1.3 / §6.2 FRP note)
    "C1-L (Mid/Hi)": "DRCMRF",
    "C1-L (Pre/Lo)": "NDRCMRF",
    "PTC1-M (Hi)": "PTRCMRF",
    "PTC1-M (Mid)": "PTRCMRF",
    "C1-H (Hi)": "DRCMRF",
    "S1-M (Hi)": "SMRF",
    "CWS-L": "NDRCMRF",              # semi-concrete; thesis treats frame like C1-L (Pre/Lo)
    "S3-L": "SMRF",                  # light steel frame
    "CHB-L": None,                   # masonry; bc quantities are 0
    "W-L": None,                     # wood; bc quantities are 0
    "N-L": "NDRCMRF",                # non-engineered; D-13 bc=0 anyway, but listed non-ductile (§6.2.4)
}

# Per-archetype provenance confidence override (default "high" from the YAML's
# Table D-13 extraction). Items the thesis does not pin precisely -> "medium".
CONFIDENCE_OVERRIDE: dict[str, str] = {
    "C1-M (Pre/Lo) FRP": "medium",   # FRP component model not separately tabulated in D-13
    "CWS-L": "medium",               # mixed concrete/wood; story-2 light frame approximated
}

# Mapping basis note appended to thesis_source for the structural beam-column rows.
_STRUCT_NOTE = {
    "DRCMRF": "ductile RCMRF (Table 6-2; §6.2.4)",
    "NDRCMRF": "non-ductile RCMRF (Table 6-2; §6.2.4)",
    "PTRCMRF": "PT RCMRF (Table 6-2; ductile fragility, PT costs)",
    "SMRF": "steel MRF (Table 6-2)",
}


def _struct_id(system: str, side: str) -> str:
    """Return the PH.S.* beam-column ID for a structural system + side ('1S'/'2S')."""
    return f"PH.S.{system}.{side}"


def _expand_story_key(key) -> list[int]:
    """Expand a YAML per_story key into a list of integer story indices.

    Handles ``int``, ``"1,2"`` (comma list), ``"3-7"`` (inclusive range), and the
    special ``"PH"`` penthouse/roof-deck label (mapped to the story above the top
    numbered floor by the caller; here returned as sentinel -1 to be resolved later).
    """
    if isinstance(key, int):
        return [key]
    s = str(key).strip()
    if s.upper() == "PH":
        return [-1]  # sentinel: penthouse, resolved to top+1 by caller
    if "-" in s:
        lo, hi = s.split("-")
        return list(range(int(lo), int(hi) + 1))
    if "," in s:
        return [int(x) for x in s.split(",")]
    return [int(s)]


# Column -> (PH.* ID or callable, P-58 quantity unit, drift|accel) mapping.
# Acceleration components are non-directional (Direction 0, offset 1 in fragility.csv);
# drift components are directional (Direction 1). 'elev'/'edist'/'diesel' are accel.
# The structural beam-column columns are resolved per-archetype via STRUCT_SYSTEM.
NONSTRUCT_MAP: dict[str, tuple[str, str, str]] = {
    # column        ->  (PH ID,            P-58 unit, demand class)
    "chb_solid":        ("PH.NS.CHB.SU",   "125 SF",  "drift"),   # solid unreinforced CHB
    "chb_perf":         ("PH.NS.CHB.PU",   "125 SF",  "drift"),   # perforated (doors/windows) unreinforced
    "curtain_wall":     ("PH.NS.CW",       "30 SF",   "drift"),
    "ceiling":          ("PH.NS.CLG.NS",   "250 SF",  "accel"),   # non-seismic suspended ceiling
    "fixtures":         ("PH.NS.FIX.NS",   "1 EA",    "accel"),   # non-seismic ceiling fixtures
    "stairs":           ("PH.NS.STAIRS",   "1 EA",    "drift"),
    "elec_dt":          ("PH.NS.ELEC.DT",  "1 EA",    "accel"),
    "elec_wm":          ("PH.NS.ELEC.WM",  "1 EA",    "accel"),
    "elev":             ("PH.NS.ELEV",     "1 EA",    "accel"),
    "sprinkler_drop":   ("PH.NS.SPR.DROP", "100 EA",  "accel"),
    "sprinkler_pipe":   ("PH.NS.SPR.PIPE", "1000 LF", "accel"),
    # steel connection sub-components (S1-M only)
    "steel_splice":     ("PH.S.SPLICE",    "1 EA",    "drift"),
    "steel_baseplate":  ("PH.S.BASEPLT",   "1 EA",    "drift"),
}

# Demand-class -> (Pelicun Direction, fragility offset). Acceleration items are
# non-directional in the thesis ("P-58 direction 3" RSS); the bundled fragility CSV
# encodes them as Direction 0 with Demand-Offset 1 (PFA from the floor above), so we
# emit Direction "0" for them and Direction "1" for drift components.
DEMAND_DIRECTION = {"drift": "1", "accel": "0"}


def build_rows() -> list[dict]:
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    cq = data["component_quantities"]
    rows: list[dict] = []

    for arch, info in cq.items():
        per_story = info.get("per_story")
        if not per_story:
            # Merged / no-independent-population archetype: handled at load time by
            # resolving to merged_into's rows. Skip here (no duplicate quantities).
            continue

        n_stories = int(info.get("stories"))
        top_numbered = max(
            (s for k in per_story for s in _expand_story_key(k) if s > 0),
            default=n_stories,
        )
        system = STRUCT_SYSTEM.get(arch)
        confidence = CONFIDENCE_OVERRIDE.get(arch, "high")

        for story_key, comps in per_story.items():
            stories = _expand_story_key(story_key)
            # Resolve penthouse sentinel to the floor above the top numbered story.
            stories = [top_numbered + 1 if s == -1 else s for s in stories]

            for col, qty in comps.items():
                q = float(qty)
                if q <= 0:
                    continue  # zero population -> no component instance

                # --- Resolve PH.* ID, unit, demand class ---
                if col in ("bc_1s", "bc_2s"):
                    if system is None:
                        # archetype has no engineered frame; D-13 should have 0 here.
                        continue
                    side = "1S" if col == "bc_1s" else "2S"
                    ph_id = _struct_id(system, side)
                    unit = "1 EA"
                    demand = "drift"
                    basis = f"Table D-13 (p.311); {_STRUCT_NOTE[system]}"
                elif col in NONSTRUCT_MAP:
                    ph_id, unit, demand = NONSTRUCT_MAP[col]
                    basis = "Table D-13 (p.311); Table 6-2 fragility basis"
                else:
                    raise ValueError(f"Unmapped component column {col!r} in {arch!r}")

                for st in stories:
                    rows.append(
                        {
                            "archetype": arch,
                            "story": st,
                            "component_id": ph_id,
                            "quantity": q,
                            "units": unit,
                            "direction": DEMAND_DIRECTION[demand],
                            "thesis_source": basis,
                            "provenance_confidence": confidence,
                        }
                    )

    return rows


def main() -> None:
    rows = build_rows()
    # Stable ordering: archetype, story, component_id
    rows.sort(key=lambda r: (r["archetype"], r["story"], r["component_id"]))

    fieldnames = [
        "archetype",
        "story",
        "component_id",
        "quantity",
        "units",
        "direction",
        "thesis_source",
        "provenance_confidence",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    n_arch = len({r["archetype"] for r in rows})
    n_ids = len({r["component_id"] for r in rows})
    print(f"Wrote {len(rows)} rows: {n_arch} archetypes, {n_ids} distinct PH.* IDs.")
    print(f"  -> {OUT_CSV}")


if __name__ == "__main__":
    main()
