"""Twenty thesis archetype factory functions.

All 20 archetypes are defined in Jeswani (2021), Chapter 4-5.  Parameters
(height, structural system, design code, fragility) trace to specific thesis
tables via docs/thesis/data/archetypes.yaml and
docs/thesis/data/archetype_fragilities.yaml.

The 5 "merged" archetypes have no independent structural model; they resolve
to their parent archetype's fragility as documented in archetypes.yaml.

References:
    Jeswani, K. K. (2021). MASc thesis, University of Toronto.
"""
from __future__ import annotations

import importlib.resources as pkg_resources
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from bayanihan.building import Building


# ---------------------------------------------------------------------------
# Resolve repo root and YAML data paths via importlib.resources (no hardcoded
# absolute paths — this resolves relative to the installed package location).
# ---------------------------------------------------------------------------
def _repo_root() -> Path:
    """Return the repository root by walking up from the package directory."""
    pkg_dir = Path(str(pkg_resources.files("bayanihan")))
    # pkg_dir = <repo>/bayanihan
    return pkg_dir.parent


def _thesis_data_path(filename: str) -> Path:
    """Return the absolute path to a file in docs/thesis/data/."""
    return _repo_root() / "docs" / "thesis" / "data" / filename


# ---------------------------------------------------------------------------
# Canonical archetype ID list — 20 archetypes from docs/thesis/data/archetypes.yaml
# ---------------------------------------------------------------------------
ARCHETYPE_IDS: list[str] = [
    # Group 1: NRHA-modelled
    "C1-L (Mid/Hi)",
    "C1-M (Hi)",
    "C1-M (Mid)",
    "C1-M (Pre/Lo)",
    "C1-M (Pre/Lo) FRP",
    # Group 2: EDP proxy
    "PTC1-M (Mid)",
    "PTC1-M (Hi)",
    # Group 3: Primary-simplified
    "C1-L (Pre/Lo)",
    "C1-H (Hi)",
    "S1-M (Hi)",
    # Group 4: Secondary-simplified
    "CWS-L",
    "S3-L",
    "CHB-L",
    "W-L",
    "N-L",
    # Group 5: Merged (no independent model — use parent fragility)
    "PC-L",
    "PTC1-M (Pre/Lo)",
    "PTC4-M (Lo)",
    "C4-L (Lo/Mid)",
    "C4-M (Mid)",
]


# ---------------------------------------------------------------------------
# Internal helpers — load YAML data once per process
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_archetypes_yaml() -> dict[str, Any]:
    """Load archetypes.yaml from docs/thesis/data/ (resolved via importlib.resources)."""
    path = _thesis_data_path("archetypes.yaml")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def _load_fragilities_yaml() -> dict[str, Any]:
    """Load archetype_fragilities.yaml from docs/thesis/data/."""
    path = _thesis_data_path("archetype_fragilities.yaml")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# Mapping from canonical archetype ID → YAML key in archetypes.yaml
_ARCHETYPE_ID_TO_YAML_KEY: dict[str, str] = {
    "C1-L (Mid/Hi)": "C1-L_MidHi",
    "C1-M (Hi)": "C1-M_Hi",
    "C1-M (Mid)": "C1-M_Mid",
    "C1-M (Pre/Lo)": "C1-M_PreLo",
    "C1-M (Pre/Lo) FRP": "C1-M_PreLo_FRP",
    "PTC1-M (Mid)": "PTC1-M_Mid",
    "PTC1-M (Hi)": "PTC1-M_Hi",
    "C1-L (Pre/Lo)": "C1-L_PreLo",
    "C1-H (Hi)": "C1-H_Hi",
    "S1-M (Hi)": "S1-M_Hi",
    "CWS-L": "CWS-L",
    "S3-L": "S3-L",
    "CHB-L": "CHB-L",
    "W-L": "W-L",
    "N-L": "N-L",
    "PC-L": "PC-L",
    "PTC1-M (Pre/Lo)": "PTC1-M_PreLo_merged",
    "PTC4-M (Lo)": "PTC4-M_Lo_merged",
    "C4-L (Lo/Mid)": "C4-L_LoMid_merged",
    "C4-M (Mid)": "C4-M_Mid_merged",
}

# Mapping from archetype ID → fragility YAML key in archetype_fragilities.yaml
# Merged archetypes resolve to their parent's fragility key.
_FRAGILITY_KEY_MAP: dict[str, str] = {
    "C1-L (Mid/Hi)": "C1-L_MidHi",
    "C1-M (Hi)": "C1-M_Hi",
    "C1-M (Mid)": "C1-M_Mid",
    "C1-M (Pre/Lo)": "C1-M_PreLo",
    "C1-M (Pre/Lo) FRP": "C1-M_PreLo_FRP",
    "PTC1-M (Mid)": "PTC1-M_Mid",
    "PTC1-M (Hi)": "PTC1-M_Hi",
    "C1-L (Pre/Lo)": "C1-L_PreLo",
    "C1-H (Hi)": "C1-H_Hi",
    "S1-M (Hi)": "S1-M_Hi",
    "CWS-L": "CWS-L",
    "S3-L": "S3-L",
    "CHB-L": "CHB-L",
    "W-L": "W-L",
    "N-L": "N-L",
    # Merged → parent fragility
    "PC-L": "C1-L_PreLo",           # merged_into: C1-L (Pre/Lo)
    "PTC1-M (Pre/Lo)": "C1-M_PreLo",   # merged_into: C1-M (Pre/Lo)
    "PTC4-M (Lo)": "PTC1-M_Mid",       # merged_into: PTC1-M (Mid)
    "C4-L (Lo/Mid)": "C1-L_MidHi",     # merged_into: C1-L (Mid/Hi)
    "C4-M (Mid)": "C1-M_Hi",           # merged_into: C1-M (Hi)
}


def _extract_scalar(field: Any, default: Any = None) -> Any:
    """Extract a scalar value from a YAML field (may be a dict with 'value' key)."""
    if field is None:
        return default
    if isinstance(field, dict):
        return field.get("value", default)
    return field


def _build_metadata_from_yaml(
    archetype_id: str,
    arch_data: dict[str, Any],
    frag_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build metadata dict from YAML archetype + fragility data."""
    is_merged = "merged_into" in arch_data

    meta: dict[str, Any] = {
        "label": arch_data.get("label", archetype_id),
        "structural_system": _extract_scalar(arch_data.get("structural_system"), ""),
        "height_class": arch_data.get("height_class", ""),
        "code_era": _extract_scalar(arch_data.get("code_era"), ""),
        "edp_method": arch_data.get("edp_method", ""),
        "city": arch_data.get("city", []),
        "is_merged": is_merged,
        "source": "docs/thesis/data/archetypes.yaml",
    }

    # Replacement cost fields — present for all 20 archetypes (added 2026-06-26
    # to fix loss_ratio=0 bug; values from archetypes.yaml which is the single
    # source of truth for floor_area, cost_per_m2, and derived replacement_cost_PHP).
    meta["total_floor_area_m2"] = _extract_scalar(arch_data.get("total_floor_area"))
    meta["cost_per_m2"] = _extract_scalar(arch_data.get("cost_per_m2"))
    meta["replacement_cost_PHP"] = _extract_scalar(arch_data.get("replacement_cost_PHP"))

    if is_merged:
        meta["merged_into"] = arch_data.get("merged_into", "")
        meta["merge_rationale"] = arch_data.get("merge_rationale", "")
        meta["fragility_source"] = meta["merged_into"]
    else:
        meta["edp_proxy_source"] = arch_data.get("edp_proxy_source")
        meta["fundamental_period_T1"] = _extract_scalar(
            arch_data.get("fundamental_period_T1")
        )
        meta["seismic_weight_kN"] = _extract_scalar(arch_data.get("seismic_weight_W"))

    if frag_data is not None:
        cf = frag_data.get("collapse_fragility", {})
        meta["collapse_fragility"] = {
            "IM_type": cf.get("IM_type", "Sa(T_avg)"),
            "T_avg_s": _extract_scalar(cf.get("T_avg")),
            "theta_median_Sa_g": _extract_scalar(cf.get("theta_median_Sa")),
            "beta_dispersion": _extract_scalar(cf.get("beta_dispersion")),
            "distribution": cf.get("distribution", "lognormal"),
        }
        meta["residual_drift_limit_pct"] = _extract_scalar(
            frag_data.get("residual_drift_limit")
        )
        meta["P_total_collapse"] = _extract_scalar(frag_data.get("P_total_collapse"))
        meta["P_soft_storey"] = _extract_scalar(frag_data.get("P_soft_storey"))
        meta["modelling_uncertainty_beta_m"] = _extract_scalar(
            frag_data.get("modelling_uncertainty_beta_m")
        )
        if is_merged:
            meta["fragility_note"] = (
                f"Merged archetype: uses fragility of '{arch_data.get('merged_into')}'"
            )

    return meta


def get_archetype(archetype_id: str, **overrides) -> Building:
    """Return a Building instance pre-configured for the specified archetype.

    Loads all parameters from docs/thesis/data/archetypes.yaml and
    docs/thesis/data/archetype_fragilities.yaml via importlib.resources.
    No values are hardcoded in Python.

    Merged archetypes resolve to their parent's collapse fragility parameters.

    Args:
        archetype_id: One of the 20 IDs in ARCHETYPE_IDS.
        **overrides: Optional Building attribute overrides (e.g., lat, lon).

    Raises:
        ValueError: If archetype_id is not in ARCHETYPE_IDS.
    """
    if archetype_id not in ARCHETYPE_IDS:
        raise ValueError(
            f"Unknown archetype: {archetype_id!r}. "
            f"Valid IDs: {ARCHETYPE_IDS}"
        )

    # Load YAML data (cached after first call)
    arch_yaml = _load_archetypes_yaml()
    frag_yaml = _load_fragilities_yaml()

    yaml_key = _ARCHETYPE_ID_TO_YAML_KEY[archetype_id]
    arch_data = arch_yaml["archetypes"][yaml_key]

    frag_key = _FRAGILITY_KEY_MAP[archetype_id]
    frag_data = frag_yaml["archetype_fragilities"].get(frag_key)

    # Extract stories (merged archetypes may not have stories defined)
    stories_raw = arch_data.get("stories")
    stories = int(_extract_scalar(stories_raw, 1))

    # Default representative site for archetype-only instantiation
    # Makati City center (overrideable)
    defaults: dict[str, Any] = {
        "lat": 14.5547,
        "lon": 121.0244,
        "year_built": 1995,
        "site_class": "D",
    }
    defaults.update(overrides)

    metadata = _build_metadata_from_yaml(archetype_id, arch_data, frag_data)

    return Building(
        archetype=archetype_id,
        stories=stories,
        year_built=int(defaults["year_built"]),
        site_class=str(defaults["site_class"]),
        lat=float(defaults["lat"]),
        lon=float(defaults["lon"]),
        metadata=metadata,
    )


def list_archetypes() -> list[str]:
    """Return the list of valid archetype IDs."""
    return list(ARCHETYPE_IDS)
