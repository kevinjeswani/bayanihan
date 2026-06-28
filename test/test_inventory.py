"""Test suite for the synthetic Manila schools demo inventory.

P4 — synthetic_inventory
Source: bayanihan/data/inventory/manila_schools_demo.geojson
Generator: utils/gen_synthetic_inventory.py (seed=2021, reproducible)

The test verifies:
  - GeoJSON loads as a valid GeoDataFrame with the required columns
  - ~50 rows (exactly 50 for a fixed seed)
  - All archetype_id values are in the 20 valid IDs
  - Latitudes/longitudes within Metro Manila bounds
  - Both cities represented (Makati, Quezon City)
  - City split roughly matches real portfolio proportions (~9-10% Makati)
  - Archetype distribution is dominated by C1 RCMRF types (>60%)
  - Generation is reproducible: running the script produces the same output
"""

from __future__ import annotations

import importlib.resources
import pathlib

import geopandas as gpd
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GEOJSON_PATH = REPO_ROOT / "bayanihan" / "data" / "inventory" / "manila_schools_demo.geojson"
GEN_SCRIPT = REPO_ROOT / "utils" / "gen_synthetic_inventory.py"

# ---------------------------------------------------------------------------
# Constants from gen_synthetic_inventory.py (duplicated minimally here)
# ---------------------------------------------------------------------------
VALID_ARCHETYPE_IDS: set[str] = {
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
}
assert len(VALID_ARCHETYPE_IDS) == 20

REQUIRED_COLUMNS = {
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
}

# Metro Manila approximate bounds (generous outer envelope)
# Makati: ~14.53–14.58°N, ~121.00–121.05°E
# QC:     ~14.59–14.74°N, ~121.01–121.12°E
MM_LAT_MIN = 14.50
MM_LAT_MAX = 14.75
MM_LON_MIN = 121.00
MM_LON_MAX = 121.15


# ---------------------------------------------------------------------------
# Fixture: load GeoDataFrame once per session
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def gdf() -> gpd.GeoDataFrame:
    assert GEOJSON_PATH.exists(), (
        f"GeoJSON not found: {GEOJSON_PATH}. "
        "Run `uv run python utils/gen_synthetic_inventory.py` to generate it."
    )
    return gpd.read_file(GEOJSON_PATH)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFileIntegrity:
    """Basic file and structure checks."""

    def test_geojson_file_exists(self) -> None:
        assert GEOJSON_PATH.exists(), f"Missing: {GEOJSON_PATH}"

    def test_loads_as_geodataframe(self, gdf: gpd.GeoDataFrame) -> None:
        assert isinstance(gdf, gpd.GeoDataFrame)

    def test_has_crs(self, gdf: gpd.GeoDataFrame) -> None:
        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 4326, f"Expected EPSG:4326, got {gdf.crs}"

    def test_geometry_type_point(self, gdf: gpd.GeoDataFrame) -> None:
        assert all(gdf.geometry.geom_type == "Point")

    def test_required_columns_present(self, gdf: gpd.GeoDataFrame) -> None:
        missing = REQUIRED_COLUMNS - set(gdf.columns)
        assert not missing, f"Missing columns: {missing}"


class TestRowCount:
    """Row count ~50 (exactly 50 for fixed seed=2021)."""

    def test_approximately_50_buildings(self, gdf: gpd.GeoDataFrame) -> None:
        assert 45 <= len(gdf) <= 55, f"Expected ~50 rows, got {len(gdf)}"

    def test_exactly_50_for_seed_2021(self, gdf: gpd.GeoDataFrame) -> None:
        """Fixed seed must produce exactly 50 buildings."""
        assert len(gdf) == 50, f"Seed=2021 should produce 50 buildings, got {len(gdf)}"


class TestArchetypeIds:
    """All archetype_id values must be valid."""

    def test_all_archetypes_valid(self, gdf: gpd.GeoDataFrame) -> None:
        invalid = set(gdf["archetype_id"].unique()) - VALID_ARCHETYPE_IDS
        assert not invalid, f"Invalid archetype IDs found: {invalid}"

    def test_no_null_archetype_ids(self, gdf: gpd.GeoDataFrame) -> None:
        assert gdf["archetype_id"].notna().all()

    def test_at_least_10_distinct_archetypes(self, gdf: gpd.GeoDataFrame) -> None:
        """With 50 buildings, expect good diversity (≥10 of 20 archetypes)."""
        n_unique = gdf["archetype_id"].nunique()
        assert n_unique >= 10, f"Expected ≥10 distinct archetypes, got {n_unique}"

    def test_c1_rcmrf_dominates(self, gdf: gpd.GeoDataFrame) -> None:
        """C1 RCMRF variants should dominate (>60% of stock), matching thesis."""
        c1_ids = {aid for aid in VALID_ARCHETYPE_IDS if aid.startswith("C1-")}
        c1_count = gdf["archetype_id"].isin(c1_ids).sum()
        frac = c1_count / len(gdf)
        assert frac > 0.60, (
            f"C1 RCMRF fraction {frac:.1%} below expected >60% "
            f"(thesis: ~73% QC RCMRF + Makati dominance)"
        )


class TestGeography:
    """Coordinates must be within Metro Manila bounds."""

    def test_lat_within_metro_manila(self, gdf: gpd.GeoDataFrame) -> None:
        assert gdf["lat"].between(MM_LAT_MIN, MM_LAT_MAX).all(), (
            f"Lat out of bounds: min={gdf['lat'].min():.4f}, max={gdf['lat'].max():.4f}"
        )

    def test_lon_within_metro_manila(self, gdf: gpd.GeoDataFrame) -> None:
        assert gdf["lon"].between(MM_LON_MIN, MM_LON_MAX).all(), (
            f"Lon out of bounds: min={gdf['lon'].min():.4f}, max={gdf['lon'].max():.4f}"
        )

    def test_geometry_coords_match_lat_lon(self, gdf: gpd.GeoDataFrame) -> None:
        """GeoJSON Point(lon, lat) should match stored lat/lon columns."""
        np.testing.assert_allclose(
            gdf.geometry.x.values,
            gdf["lon"].values,
            atol=1e-5,
            err_msg="Geometry x (lon) does not match lon column",
        )
        np.testing.assert_allclose(
            gdf.geometry.y.values,
            gdf["lat"].values,
            atol=1e-5,
            err_msg="Geometry y (lat) does not match lat column",
        )


class TestCitySplit:
    """Both cities must be represented; split should be realistic."""

    def test_both_cities_present(self, gdf: gpd.GeoDataFrame) -> None:
        cities = set(gdf["city"].unique())
        assert "Makati" in cities, "Makati missing from city column"
        assert "Quezon City" in cities, "Quezon City missing from city column"

    def test_quezon_city_dominates(self, gdf: gpd.GeoDataFrame) -> None:
        """QC has ~90% of real buildings; synthetic should reflect this."""
        qc_frac = (gdf["city"] == "Quezon City").mean()
        assert qc_frac >= 0.80, (
            f"QC fraction {qc_frac:.1%} too low; expected ≥80% "
            f"(real portfolio: QC=925/1021≈90.6%)"
        )

    def test_makati_has_buildings(self, gdf: gpd.GeoDataFrame) -> None:
        mkt = (gdf["city"] == "Makati").sum()
        assert mkt >= 3, f"Makati should have ≥3 buildings, got {mkt}"

    def test_makati_lat_in_range(self, gdf: gpd.GeoDataFrame) -> None:
        mkt = gdf[gdf["city"] == "Makati"]
        assert mkt["lat"].between(14.53, 14.58).all(), (
            "Makati latitudes out of expected range [14.53, 14.58]"
        )

    def test_qc_lat_in_range(self, gdf: gpd.GeoDataFrame) -> None:
        qc = gdf[gdf["city"] == "Quezon City"]
        assert qc["lat"].between(14.60, 14.73).all(), (
            "QC latitudes out of expected range [14.60, 14.73]"
        )


class TestBuildingAttributes:
    """Sanity checks on per-building attribute values."""

    def test_stories_positive_integer(self, gdf: gpd.GeoDataFrame) -> None:
        assert (gdf["stories"] >= 1).all()
        assert (gdf["stories"] <= 15).all()
        assert gdf["stories"].dtype in (int, "int64", "int32")

    def test_year_built_plausible(self, gdf: gpd.GeoDataFrame) -> None:
        assert (gdf["year_built"] >= 1900).all()
        assert (gdf["year_built"] <= 2025).all()

    def test_site_class_valid(self, gdf: gpd.GeoDataFrame) -> None:
        valid = {"SA", "SB", "SC", "SD", "SE", "SF"}
        invalid = set(gdf["site_class"].unique()) - valid
        assert not invalid, f"Invalid site class values: {invalid}"

    def test_replacement_cost_positive(self, gdf: gpd.GeoDataFrame) -> None:
        assert (gdf["replacement_cost_php"] > 0).all()

    def test_replacement_cost_plausible(self, gdf: gpd.GeoDataFrame) -> None:
        """Costs should be above ₱50k (min useful) and below ₱10B (max realistic)."""
        assert (gdf["replacement_cost_php"] >= 50_000).all()
        assert (gdf["replacement_cost_php"] <= 10_000_000_000).all()

    def test_ids_unique(self, gdf: gpd.GeoDataFrame) -> None:
        assert gdf["id"].nunique() == len(gdf), "Building IDs are not unique"

    def test_id_format(self, gdf: gpd.GeoDataFrame) -> None:
        """IDs should follow SCH_NNN pattern."""
        import re
        pattern = re.compile(r"^SCH_\d{3}$")
        assert gdf["id"].apply(lambda x: bool(pattern.match(x))).all(), (
            "Some IDs do not match pattern SCH_NNN"
        )


class TestReproducibility:
    """Running the generator twice must produce identical output."""

    def test_same_seed_same_output(self, tmp_path: pathlib.Path) -> None:
        """Import and call generate() twice; both runs must be byte-identical."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("gen_syn", GEN_SCRIPT)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        out1 = tmp_path / "run1.geojson"
        out2 = tmp_path / "run2.geojson"

        gdf1 = mod.generate(out1)
        gdf2 = mod.generate(out2)

        # Re-read from disk to test file-level reproducibility
        g1 = gpd.read_file(out1)
        g2 = gpd.read_file(out2)

        assert len(g1) == len(g2), "Row counts differ between runs"
        assert list(g1["id"]) == list(g2["id"]), "IDs differ between runs"
        assert list(g1["archetype_id"]) == list(g2["archetype_id"]), (
            "Archetype IDs differ between runs"
        )
        np.testing.assert_array_equal(
            g1["lat"].values, g2["lat"].values, err_msg="Lats differ between runs"
        )
        np.testing.assert_array_equal(
            g1["lon"].values, g2["lon"].values, err_msg="Lons differ between runs"
        )

    def test_committed_file_matches_fresh_generation(self, tmp_path: pathlib.Path) -> None:
        """The committed GeoJSON must match a fresh generation from the same seed."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("gen_syn", GEN_SCRIPT)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        fresh_path = tmp_path / "fresh.geojson"
        mod.generate(fresh_path)

        committed = gpd.read_file(GEOJSON_PATH)
        fresh = gpd.read_file(fresh_path)

        assert len(committed) == len(fresh), (
            f"Committed file has {len(committed)} rows but fresh generation has {len(fresh)}. "
            "Did you forget to re-run the generator after changing the script?"
        )
        assert list(committed["id"]) == list(fresh["id"]), (
            "IDs in committed file differ from fresh generation."
        )
        assert list(committed["archetype_id"]) == list(fresh["archetype_id"]), (
            "Archetype IDs in committed file differ from fresh generation."
        )
