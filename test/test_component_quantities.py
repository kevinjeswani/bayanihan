"""Tests for the per-archetype FEMA P-58 component-quantity inventory.

Covers the packaged table (``bayanihan/data/component_quantities.csv``,
generated from thesis Table D-13) and the building.py loader that replaces the
generic ``_DEFAULT_CMP_INVENTORY`` placeholder with each archetype's REAL component
population. Asserts:

1. Every portfolio archetype loads a NON-placeholder inventory.
2. Every component ID in every archetype's marginals resolves in BOTH the fragility
   and consequence DBs.
3. Merged archetypes (e.g. ``C4-M (Mid)``) inherit their parent's population.
4. The repair-class spread is populated (rc1 + at least one of rc2/rc3) for the
   major engineered archetypes, so the REDi milestones can differentiate.
5. Provenance flags are present on every row.

Source: docs/thesis/data/component_quantities.yaml (Table D-13, printed p.311);
mapping basis Table 6-2 (§6.2.2) — see utils/build_component_quantities_csv.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from bayanihan.archetypes import ARCHETYPE_IDS
from bayanihan.building import (
    _DEFAULT_CMP_INVENTORY,
    _build_cmp_marginals,
    _load_component_table,
    _merged_archetype_map,
    _resolve_component_archetype,
)
from bayanihan.recovery import _component_repair_class

REPO = Path(__file__).parent.parent
DATA_DIR = REPO / "bayanihan" / "data"
COMPONENT_CSV = DATA_DIR / "component_quantities.csv"
FRAGILITY_CSV = DATA_DIR / "fragility.csv"
CONSEQUENCE_CSV = DATA_DIR / "consequence_repair.csv"

# The 14 archetypes that actually appear in the real 1,021-building inventory.
# (Merged archetypes C4-* appear only in the demo inventory and resolve to parents.)
PORTFOLIO_ARCHETYPES = [
    "C1-M (Hi)", "C1-M (Mid)", "C1-M (Pre/Lo)", "C1-L (Mid/Hi)", "C1-L (Pre/Lo)",
    "PTC1-M (Hi)", "PTC1-M (Mid)", "C1-H (Hi)", "S1-M (Hi)",
    "CWS-L", "S3-L", "CHB-L", "W-L", "N-L",
]

# Engineered archetypes that must show a multi-class repair spread (rc2 or rc3 > 0)
# so the three REDi recovery milestones differentiate. Bare wood/nipa (W-L, N-L)
# and the smallest masonry have legitimately sparse populations and are excluded.
MULTICLASS_ARCHETYPES = [
    "C1-M (Hi)", "C1-M (Mid)", "C1-M (Pre/Lo)", "C1-L (Mid/Hi)", "C1-L (Pre/Lo)",
    "PTC1-M (Hi)", "PTC1-M (Mid)", "C1-H (Hi)", "S1-M (Hi)", "CWS-L",
]


@pytest.fixture(scope="module")
def fragility_ids() -> set[str]:
    return set(pd.read_csv(FRAGILITY_CSV)["ID"])


@pytest.fixture(scope="module")
def consequence_base_ids() -> set[str]:
    cons = pd.read_csv(CONSEQUENCE_CSV)
    # consequence IDs are "<base>-Cost" / "<base>-Time"
    return {str(x).rsplit("-", 1)[0] for x in cons["ID"]}


# ---------------------------------------------------------------------------
# Packaged artifact
# ---------------------------------------------------------------------------

def test_component_csv_exists():
    assert COMPONENT_CSV.is_file(), "component_quantities.csv must be packaged"


def test_component_table_loads_nonempty():
    df = _load_component_table()
    assert not df.empty
    for col in ("archetype", "story", "component_id", "quantity", "units",
                "direction", "thesis_source", "provenance_confidence"):
        assert col in df.columns


def test_all_portfolio_archetypes_present_in_table():
    df = _load_component_table()
    present = set(df["archetype"])
    missing = [a for a in PORTFOLIO_ARCHETYPES if a not in present]
    assert not missing, f"archetypes missing component populations: {missing}"


def test_every_quantity_positive():
    df = _load_component_table()
    assert (df["quantity"] > 0).all(), "all component quantities must be > 0"


def test_provenance_on_every_row():
    df = _load_component_table()
    assert df["thesis_source"].notna().all()
    assert df["provenance_confidence"].notna().all()
    assert set(df["provenance_confidence"]).issubset({"high", "medium", "low"})


def test_all_ids_resolve_in_dbs(fragility_ids, consequence_base_ids):
    """Every component_id in the table resolves in fragility AND consequence DBs."""
    df = _load_component_table()
    used = set(df["component_id"])
    assert used <= fragility_ids, f"IDs not in fragility DB: {used - fragility_ids}"
    assert used <= consequence_base_ids, (
        f"IDs not in consequence DB: {used - consequence_base_ids}"
    )


# ---------------------------------------------------------------------------
# building.py loader / marginals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("archetype_id", PORTFOLIO_ARCHETYPES)
def test_marginals_are_archetype_specific(archetype_id):
    """Each portfolio archetype must load its OWN Table D-13 population, not the placeholder.

    The placeholder (_DEFAULT_CMP_INVENTORY) is applied at Location=='all' with a fixed
    generic 6-component set; a real per-archetype population is placed at specific
    per-story Location values and matches component_quantities.csv for that archetype.

    NOTE (P7, 2026-06-27): the previous assertion required the marginals to be *larger*
    than the placeholder (``len(m) > len(_DEFAULT_CMP_INVENTORY)`` OR an ID outside the
    placeholder set). That was wrong for legitimately minimal archetypes — CHB-L (4 cmp),
    W-L / N-L (2 cmp each, ceiling + fixtures) are correct small SUBSETS of the 6-component
    placeholder, so both clauses were false and the test failed despite the population being
    perfectly archetype-specific. The correct discriminator is per-story ``Location`` +
    an exact match to the table rows for THIS archetype (story-truncated to building height),
    which holds for both minimal and large archetypes.
    """
    from bayanihan.building import Building

    b = Building.from_archetype(archetype_id)
    m = _build_cmp_marginals(b.stories, archetype_id)
    assert not m.empty
    # Placeholder always uses Location='all'; a real population uses story numbers.
    assert not (m["Location"] == "all").all(), (
        f"{archetype_id} fell back to the placeholder inventory (Location=='all')"
    )
    assert (m["Location"] != "all").all(), (
        f"{archetype_id}: every marginal must sit at a specific story Location"
    )

    # The marginals must reproduce the archetype's OWN Table D-13 rows that fit within
    # the building height — keyed by (component_id, story, direction) with matching qty.
    table = _load_component_table()
    resolved = _resolve_component_archetype(archetype_id)
    expected = table[(table["archetype"] == resolved) & (table["story"] <= b.stories)]
    assert not expected.empty, f"{archetype_id}: no table rows within building height"

    got = {
        (str(cid), str(loc), str(direction)): float(theta0)
        for cid, loc, direction, theta0 in zip(
            m.index, m["Location"], m["Direction"], m["Theta_0"]
        )
    }
    want = {
        (str(r.component_id), str(int(r.story)), str(r.direction)): float(r.quantity)
        for r in expected.itertuples(index=False)
    }
    assert got == want, (
        f"{archetype_id}: marginals do not match the Table D-13 population "
        f"(missing {set(want) - set(got)}; extra {set(got) - set(want)})"
    )


@pytest.mark.parametrize("archetype_id", PORTFOLIO_ARCHETYPES)
def test_marginal_ids_resolve(archetype_id, fragility_ids, consequence_base_ids):
    """All component IDs in an archetype's marginals resolve in both DBs."""
    from bayanihan.building import Building

    b = Building.from_archetype(archetype_id)
    m = _build_cmp_marginals(b.stories, archetype_id)
    ids = set(m.index)
    assert ids <= fragility_ids, f"{archetype_id}: {ids - fragility_ids} not in fragility"
    assert ids <= consequence_base_ids, (
        f"{archetype_id}: {ids - consequence_base_ids} not in consequence"
    )


@pytest.mark.parametrize("archetype_id", PORTFOLIO_ARCHETYPES)
def test_marginal_locations_within_building(archetype_id):
    """No component is placed on a story above the building height."""
    from bayanihan.building import Building

    b = Building.from_archetype(archetype_id)
    m = _build_cmp_marginals(b.stories, archetype_id)
    locs = [loc for loc in m["Location"] if loc != "all"]
    for loc in locs:
        assert 1 <= int(loc) <= b.stories, (
            f"{archetype_id}: component at story {loc} > stories {b.stories}"
        )


@pytest.mark.parametrize("archetype_id", MULTICLASS_ARCHETYPES)
def test_repair_class_spread(archetype_id):
    """Engineered archetypes must populate rc1 AND (rc2 or rc3) so milestones split."""
    from bayanihan.building import Building

    b = Building.from_archetype(archetype_id)
    m = _build_cmp_marginals(b.stories, archetype_id)
    classes = {_component_repair_class(str(cid)) for cid in m.index}
    assert 1 in classes, f"{archetype_id}: no Repair Class 1 component"
    assert classes & {2, 3}, (
        f"{archetype_id}: only Repair Class 1 present -> milestones cannot differentiate"
    )


# ---------------------------------------------------------------------------
# Merged-archetype resolution
# ---------------------------------------------------------------------------

def test_merged_map_nonempty():
    mm = _merged_archetype_map()
    assert mm, "merged-archetype map should be populated from the YAML"
    # Known merges from component_quantities.yaml
    assert mm.get("C4-M (Mid)") == "C1-M (Hi)"
    assert mm.get("C4-L (Lo/Mid)") == "C1-L (Mid/Hi)"


def test_merged_archetype_inherits_parent_population():
    """A merged archetype resolves to (and loads) its parent's component IDs."""
    from bayanihan.building import Building

    parent = _resolve_component_archetype("C4-M (Mid)")
    assert parent == "C1-M (Hi)"

    b = Building.from_archetype("C4-M (Mid)")
    m = _build_cmp_marginals(b.stories, "C4-M (Mid)")
    assert not m.empty
    assert not (m["Location"] == "all").all(), "merged archetype hit the placeholder"
    # IDs must be a subset of the parent's full population (story-truncated is OK).
    table = _load_component_table()
    parent_ids = set(table[table["archetype"] == "C1-M (Hi)"]["component_id"])
    assert set(m.index) <= parent_ids


def test_unknown_archetype_falls_back_to_placeholder():
    """An archetype with no table row uses the placeholder (Location='all')."""
    m = _build_cmp_marginals(3, "TOTALLY-UNKNOWN-ARCHETYPE")
    assert not m.empty
    assert (m["Location"] == "all").all()
    assert set(m.index) == set(_DEFAULT_CMP_INVENTORY)
