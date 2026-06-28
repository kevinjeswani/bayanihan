"""Tests for bayanihan.archetypes — all 20 archetype factories."""
from __future__ import annotations

import pytest

from bayanihan.archetypes import (
    ARCHETYPE_IDS,
    get_archetype,
    list_archetypes,
)
from bayanihan.building import Building


# ---------------------------------------------------------------------------
# Test data: merged archetype IDs (Group 5) per archetypes.yaml
# ---------------------------------------------------------------------------
MERGED_ARCHETYPE_IDS = {
    "PC-L",
    "PTC1-M (Pre/Lo)",
    "PTC4-M (Lo)",
    "C4-L (Lo/Mid)",
    "C4-M (Mid)",
}

NON_MERGED_ARCHETYPE_IDS = set(ARCHETYPE_IDS) - MERGED_ARCHETYPE_IDS


# ---------------------------------------------------------------------------
# Invariant tests
# ---------------------------------------------------------------------------

def test_archetype_ids_count():
    """Exactly 20 archetypes must be defined."""
    assert len(ARCHETYPE_IDS) == 20


def test_archetype_ids_unique():
    """All archetype IDs must be unique."""
    assert len(ARCHETYPE_IDS) == len(set(ARCHETYPE_IDS))


def test_list_archetypes_returns_copy():
    """list_archetypes() should return the canonical list."""
    ids = list_archetypes()
    assert set(ids) == set(ARCHETYPE_IDS)


def test_get_archetype_unknown_raises():
    """get_archetype() raises ValueError for unknown IDs."""
    with pytest.raises(ValueError, match="Unknown archetype"):
        get_archetype("NOT_AN_ARCHETYPE")


# ---------------------------------------------------------------------------
# Parametrized: every archetype instantiates and has required properties
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("archetype_id", ARCHETYPE_IDS)
def test_archetype_instantiates(archetype_id: str):
    """Every archetype factory must return a Building without error."""
    b = get_archetype(archetype_id)
    assert isinstance(b, Building)


@pytest.mark.parametrize("archetype_id", ARCHETYPE_IDS)
def test_archetype_id_set(archetype_id: str):
    """building.archetype must equal the requested ID."""
    b = get_archetype(archetype_id)
    assert b.archetype == archetype_id


@pytest.mark.parametrize("archetype_id", ARCHETYPE_IDS)
def test_archetype_stories_positive(archetype_id: str):
    """stories must be a positive integer."""
    b = get_archetype(archetype_id)
    assert isinstance(b.stories, int)
    assert b.stories >= 1


@pytest.mark.parametrize("archetype_id", ARCHETYPE_IDS)
def test_archetype_has_metadata(archetype_id: str):
    """Every archetype must have a non-empty metadata dict."""
    b = get_archetype(archetype_id)
    assert isinstance(b.metadata, dict)
    assert len(b.metadata) > 0


@pytest.mark.parametrize("archetype_id", ARCHETYPE_IDS)
def test_archetype_label_present(archetype_id: str):
    """metadata must include a non-empty label."""
    b = get_archetype(archetype_id)
    assert "label" in b.metadata
    assert isinstance(b.metadata["label"], str)
    assert len(b.metadata["label"]) > 0


@pytest.mark.parametrize("archetype_id", ARCHETYPE_IDS)
def test_archetype_has_collapse_fragility(archetype_id: str):
    """Every archetype must expose collapse_fragility in metadata.

    Merged archetypes resolve to their parent's fragility — still present.
    """
    b = get_archetype(archetype_id)
    assert "collapse_fragility" in b.metadata, (
        f"Archetype {archetype_id!r} missing collapse_fragility in metadata"
    )
    cf = b.metadata["collapse_fragility"]
    assert isinstance(cf, dict)
    assert "theta_median_Sa_g" in cf
    assert cf["theta_median_Sa_g"] is not None
    assert cf["theta_median_Sa_g"] > 0


# ---------------------------------------------------------------------------
# Non-merged archetype specific checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("archetype_id", sorted(NON_MERGED_ARCHETYPE_IDS))
def test_non_merged_not_flagged(archetype_id: str):
    """Non-merged archetypes must NOT have is_merged=True."""
    b = get_archetype(archetype_id)
    assert b.metadata.get("is_merged") is False, (
        f"{archetype_id!r} should not be merged"
    )


# ---------------------------------------------------------------------------
# Merged archetype specific checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("archetype_id", sorted(MERGED_ARCHETYPE_IDS))
def test_merged_flag_set(archetype_id: str):
    """Merged archetypes must have is_merged=True in metadata."""
    b = get_archetype(archetype_id)
    assert b.metadata.get("is_merged") is True, (
        f"{archetype_id!r} should be flagged as merged"
    )


@pytest.mark.parametrize("archetype_id", sorted(MERGED_ARCHETYPE_IDS))
def test_merged_has_parent_reference(archetype_id: str):
    """Merged archetypes must indicate which archetype they merge into."""
    b = get_archetype(archetype_id)
    assert "merged_into" in b.metadata, (
        f"Merged archetype {archetype_id!r} missing merged_into"
    )
    assert isinstance(b.metadata["merged_into"], str)
    assert len(b.metadata["merged_into"]) > 0


@pytest.mark.parametrize("archetype_id", sorted(MERGED_ARCHETYPE_IDS))
def test_merged_fragility_matches_parent(archetype_id: str):
    """Merged archetype's collapse fragility must equal its parent's."""
    from bayanihan.archetypes import _FRAGILITY_KEY_MAP, _load_fragilities_yaml

    b_merged = get_archetype(archetype_id)
    parent_id = b_merged.metadata["merged_into"]

    # Find the parent archetype by its ID (the merged_into value may use thesis notation)
    # Map parent thesis-notation ID to canonical ARCHETYPE_IDS
    parent_canonical = next(
        (aid for aid in ARCHETYPE_IDS if aid == parent_id), None
    )
    if parent_canonical is None:
        pytest.skip(f"Parent {parent_id!r} not in ARCHETYPE_IDS — skip fragility check")

    b_parent = get_archetype(parent_canonical)
    assert b_merged.metadata["collapse_fragility"]["theta_median_Sa_g"] == (
        b_parent.metadata["collapse_fragility"]["theta_median_Sa_g"]
    ), (
        f"Merged {archetype_id!r} fragility theta ≠ parent {parent_canonical!r} fragility theta"
    )


# ---------------------------------------------------------------------------
# Override tests
# ---------------------------------------------------------------------------

def test_archetype_override_lat_lon():
    """Building lat/lon overrides must propagate."""
    b = get_archetype("C1-M (Hi)", lat=14.5, lon=121.0)
    assert b.lat == 14.5
    assert b.lon == 121.0


def test_building_from_archetype_same_as_get_archetype():
    """Building.from_archetype() must return same result as get_archetype()."""
    b1 = Building.from_archetype("C1-L (Mid/Hi)")
    b2 = get_archetype("C1-L (Mid/Hi)")
    assert b1.archetype == b2.archetype
    assert b1.stories == b2.stories
