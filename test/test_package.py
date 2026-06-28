"""Smoke tests — package imports and basic invariants."""
import pytest
import bayanihan


def test_version_set():
    assert bayanihan.__version__ == "0.0.0"


def test_module_imports():
    from bayanihan import building, archetypes, portfolio, hazard, recovery
    assert building is not None
    assert archetypes is not None
    assert portfolio is not None
    assert hazard is not None
    assert recovery is not None


def test_archetype_ids_count():
    from bayanihan.archetypes import ARCHETYPE_IDS
    assert len(ARCHETYPE_IDS) == 20, f"Expected 20 archetypes, got {len(ARCHETYPE_IDS)}"


def test_archetype_ids_unique():
    from bayanihan.archetypes import ARCHETYPE_IDS
    assert len(ARCHETYPE_IDS) == len(set(ARCHETYPE_IDS)), "Duplicate archetype IDs"


def test_unknown_archetype_raises():
    from bayanihan.archetypes import get_archetype
    with pytest.raises(ValueError, match="Unknown archetype"):
        get_archetype("NOT_AN_ARCHETYPE")


def test_hazard_model_is_abstract():
    from bayanihan.hazard import HazardModel
    with pytest.raises(TypeError):
        HazardModel()
