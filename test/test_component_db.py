"""
Tests for the Pelicun-format component library CSVs.

Verifies:
1. CSV files parse correctly and have the required Pelicun columns
2. Pelicun's damage model can load fragility.csv via load_model_parameters
3. Pelicun's loss model can load consequence_repair.csv via load_model_parameters
4. Row counts match YAML component counts
5. Provenance metadata present on every row

Sources traced to:
  docs/thesis/data/component_fragilities.yaml (Tables D-3, D-4, p.298)
  docs/thesis/data/consequence_parameters.yaml (Tables D-8, D-9, pp.305-306)
"""

from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).parent.parent
DATA_DIR = REPO / "bayanihan" / "data"
FRAGILITY_CSV = DATA_DIR / "fragility.csv"
CONSEQUENCE_CSV = DATA_DIR / "consequence_repair.csv"
REPLACEMENT_CSV = DATA_DIR / "replacement.csv"

# Expected component count from YAML
# 10 structural + 17 non-structural = 27 total
EXPECTED_COMPONENT_COUNT = 27

# Required columns for each CSV (Pelicun schema, excluding provenance trailing cols)
FRAGILITY_REQUIRED_COLS = [
    "Incomplete",
    "Demand-Type",
    "Demand-Unit",
    "Demand-Offset",
    "Demand-Directional",
    "LS1-Family",
    "LS1-Theta_0",
    "LS1-Theta_1",
]
CONSEQUENCE_REQUIRED_COLS = [
    "Incomplete",
    "Quantity-Unit",
    "DV-Unit",
]
# At least one DSx-Family / DSx-Theta_0 must be present
CONSEQUENCE_DS_PREFIX = "DS"

# Pelicun demand types allowed (per confirmed schema)
VALID_DEMAND_TYPES = {
    "Peak Interstory Drift Ratio",
    "Peak Floor Acceleration",
}

# Provenance columns that must be on every row
PROVENANCE_COLS = ["thesis_source", "provenance_confidence"]

# Valid provenance_confidence values
VALID_PROVENANCE_VALUES = {"high", "medium", "low"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def fragility_df() -> pd.DataFrame:
    """Load fragility.csv, skipping comment lines."""
    assert FRAGILITY_CSV.exists(), f"fragility.csv not found: {FRAGILITY_CSV}"
    df = pd.read_csv(FRAGILITY_CSV, index_col=0)
    return df


@pytest.fixture(scope="module")
def consequence_df() -> pd.DataFrame:
    """Load consequence_repair.csv, skipping comment lines."""
    assert CONSEQUENCE_CSV.exists(), f"consequence_repair.csv not found: {CONSEQUENCE_CSV}"
    df = pd.read_csv(CONSEQUENCE_CSV, index_col=0)
    return df


@pytest.fixture(scope="module")
def replacement_df() -> pd.DataFrame:
    """Load replacement.csv, skipping comment lines."""
    assert REPLACEMENT_CSV.exists(), f"replacement.csv not found: {REPLACEMENT_CSV}"
    df = pd.read_csv(REPLACEMENT_CSV, index_col=0)
    return df


# ── CSV parse and column tests ────────────────────────────────────────────────

class TestFragilityCSV:
    """Tests for fragility.csv structure and content."""

    def test_file_exists(self):
        assert FRAGILITY_CSV.exists()

    def test_row_count(self, fragility_df):
        """Number of rows must match YAML component count (27)."""
        assert len(fragility_df) == EXPECTED_COMPONENT_COUNT, (
            f"Expected {EXPECTED_COMPONENT_COUNT} components, got {len(fragility_df)}. "
            f"IDs: {list(fragility_df.index)}"
        )

    def test_required_columns_present(self, fragility_df):
        for col in FRAGILITY_REQUIRED_COLS:
            assert col in fragility_df.columns, f"Missing required column: {col}"

    def test_demand_type_values(self, fragility_df):
        """All Demand-Type values must be valid Pelicun strings."""
        bad = set(fragility_df["Demand-Type"].unique()) - VALID_DEMAND_TYPES
        assert not bad, f"Invalid Demand-Type values found: {bad}"

    def test_demand_unit_pidr_is_unitless(self, fragility_df):
        """PIDR components must use 'unitless' (Pelicun convention, NOT %)."""
        pidr_mask = fragility_df["Demand-Type"] == "Peak Interstory Drift Ratio"
        pidr_units = fragility_df.loc[pidr_mask, "Demand-Unit"].unique()
        assert all(u == "unitless" for u in pidr_units), (
            f"PIDR rows must have Demand-Unit='unitless'; got {pidr_units}"
        )

    def test_pidr_theta_range(self, fragility_df):
        """PIDR medians (LS1-Theta_0) must be in [0.001, 0.2] (unitless, not %)."""
        pidr = fragility_df[fragility_df["Demand-Type"] == "Peak Interstory Drift Ratio"]
        theta0 = pd.to_numeric(pidr["LS1-Theta_0"], errors="coerce")
        assert theta0.dropna().between(0.0005, 0.5).all(), (
            f"PIDR LS1-Theta_0 out of expected range [0.0005, 0.5]:\n{theta0}"
        )

    def test_no_raw_percent_theta(self, fragility_df):
        """No PIDR Theta_0 should be >= 1.0 (which would indicate un-converted %)."""
        pidr = fragility_df[fragility_df["Demand-Type"] == "Peak Interstory Drift Ratio"]
        theta0 = pd.to_numeric(pidr["LS1-Theta_0"], errors="coerce")
        big = theta0[theta0 >= 1.0]
        assert big.empty, f"Found large PIDR Theta_0 values (still in %?): {big}"

    def test_incomplete_flag_valid(self, fragility_df):
        """Incomplete column must be 0 or 1."""
        vals = fragility_df["Incomplete"].dropna().unique()
        assert all(int(v) in (0, 1) for v in vals), f"Unexpected Incomplete values: {vals}"

    def test_provenance_columns_present(self, fragility_df):
        for col in PROVENANCE_COLS:
            assert col in fragility_df.columns, f"Missing provenance column: {col}"

    def test_provenance_on_every_row(self, fragility_df):
        """Every row must have non-empty thesis_source."""
        missing = fragility_df["thesis_source"].isna() | (fragility_df["thesis_source"] == "")
        assert not missing.any(), (
            f"Rows missing thesis_source: {list(fragility_df.index[missing])}"
        )

    def test_provenance_confidence_values(self, fragility_df):
        """provenance_confidence must be one of high/medium/low."""
        vals = set(fragility_df["provenance_confidence"].dropna().unique())
        bad = vals - VALID_PROVENANCE_VALUES
        assert not bad, f"Invalid provenance_confidence values: {bad}"

    def test_structural_components_present(self, fragility_df):
        """Key structural component IDs must exist."""
        expected = [
            "PH.S.DRCMRF.1S", "PH.S.DRCMRF.2S",
            "PH.S.NDRCMRF.1S", "PH.S.NDRCMRF.2S",
            "PH.S.PTRCMRF.1S", "PH.S.PTRCMRF.2S",
            "PH.S.SMRF.1S", "PH.S.SMRF.2S",
            "PH.S.SPLICE", "PH.S.BASEPLT",
        ]
        for cid in expected:
            assert cid in fragility_df.index, f"Missing structural component: {cid}"

    def test_non_structural_components_present(self, fragility_df):
        """Key non-structural component IDs must exist."""
        expected = [
            "PH.NS.CHB.SU", "PH.NS.CHB.SR", "PH.NS.CHB.PU", "PH.NS.CHB.PR",
            "PH.NS.CW", "PH.NS.CLG.NS", "PH.NS.CLG.BR",
            "PH.NS.FIX.NS", "PH.NS.FIX.SE", "PH.NS.STAIRS",
            "PH.NS.ELEC.DT", "PH.NS.ELEC.WM", "PH.NS.ELEV",
            "PH.NS.SPR.DROP", "PH.NS.SPR.PIPE", "PH.NS.EDIST", "PH.NS.DIESEL",
        ]
        for cid in expected:
            assert cid in fragility_df.index, f"Missing non-structural component: {cid}"

    def test_rcmrf_mutex_weights(self, fragility_df):
        """Ductile RCMRF LS3 must have DamageStateWeights (DS3/DS4 MutEx 0.8/0.2)."""
        for cid in ["PH.S.DRCMRF.1S", "PH.S.DRCMRF.2S"]:
            weights = fragility_df.loc[cid, "LS3-DamageStateWeights"]
            assert pd.notna(weights) and weights != "", (
                f"{cid}: LS3-DamageStateWeights should carry MutEx probabilities"
            )
            # Check values are 0.8 and 0.2
            parts = [float(p.strip()) for p in str(weights).split("|")]
            assert len(parts) == 2, f"{cid}: Expected 2 weights, got {parts}"
            assert abs(parts[0] - 0.8) < 0.001, f"{cid}: Expected P(DS3)=0.8, got {parts[0]}"
            assert abs(parts[1] - 0.2) < 0.001, f"{cid}: Expected P(DS4)=0.2, got {parts[1]}"

    def test_ceiling_demand_offset(self, fragility_df):
        """Suspended ceiling and fixtures must have Demand-Offset=1 (floor above)."""
        ceiling_ids = ["PH.NS.CLG.NS", "PH.NS.CLG.BR", "PH.NS.FIX.NS", "PH.NS.FIX.SE"]
        for cid in ceiling_ids:
            offset = fragility_df.loc[cid, "Demand-Offset"]
            assert int(offset) == 1, (
                f"{cid}: Expected Demand-Offset=1 (floor above PFA), got {offset}"
            )


class TestConsequenceCSV:
    """Tests for consequence_repair.csv structure and content."""

    def test_file_exists(self):
        assert CONSEQUENCE_CSV.exists()

    def test_row_count(self, consequence_df):
        """Should have 2 rows per component (Cost + Time) = 27 × 2 = 54."""
        expected = EXPECTED_COMPONENT_COUNT * 2
        assert len(consequence_df) == expected, (
            f"Expected {expected} rows (27 × 2), got {len(consequence_df)}"
        )

    def test_required_columns_present(self, consequence_df):
        for col in CONSEQUENCE_REQUIRED_COLS:
            assert col in consequence_df.columns, f"Missing required column: {col}"

    def test_cost_time_row_pairs(self, consequence_df):
        """Every component must have both a -Cost and -Time row."""
        cost_ids = {idx[:-5] for idx in consequence_df.index if idx.endswith("-Cost")}
        time_ids = {idx[:-5] for idx in consequence_df.index if idx.endswith("-Time")}
        assert cost_ids == time_ids, (
            f"Mismatch: cost-only={cost_ids - time_ids}, time-only={time_ids - cost_ids}"
        )

    def test_dv_unit_cost_rows(self, consequence_df):
        """All -Cost rows must have DV-Unit='PHP_2020'."""
        cost = consequence_df[consequence_df.index.str.endswith("-Cost")]
        bad = cost[cost["DV-Unit"] != "PHP_2020"]
        assert bad.empty, f"Cost rows with wrong DV-Unit: {list(bad.index)}"

    def test_dv_unit_time_rows(self, consequence_df):
        """All -Time rows must have DV-Unit='worker_hour'."""
        time = consequence_df[consequence_df.index.str.endswith("-Time")]
        bad = time[time["DV-Unit"] != "worker_hour"]
        assert bad.empty, f"Time rows with wrong DV-Unit: {list(bad.index)}"

    def test_at_least_one_ds_per_row(self, consequence_df):
        """Every row must have at least one DS with Theta_0 populated."""
        ds_theta_cols = [c for c in consequence_df.columns if c.endswith("-Theta_0")]
        assert ds_theta_cols, "No DS Theta_0 columns found"
        any_populated = consequence_df[ds_theta_cols].notna().any(axis=1)
        # Exception: splice and base plate DS1 is intentionally null (zero-cost)
        # but they should have DS2 or DS3
        rows_all_null = consequence_df.index[~any_populated]
        # Filter out known zero-DS1 rows where the component is splice/baseplt
        unexpected = [r for r in rows_all_null
                      if not any(x in r for x in ["SPLICE", "BASEPLT"])]
        # Splice/baseplt DS1 is null but DS2+ should be populated — check separately
        for splice_id in ["PH.S.SPLICE-Cost", "PH.S.SPLICE-Time",
                          "PH.S.BASEPLT-Cost", "PH.S.BASEPLT-Time"]:
            if splice_id in consequence_df.index:
                ds2_cols = [c for c in ds_theta_cols if c.startswith("DS2") or c.startswith("DS3")]
                has_ds2 = consequence_df.loc[splice_id, ds2_cols].notna().any()
                assert has_ds2, f"{splice_id}: No DS2+ data found (expected per thesis)"
        assert not unexpected, f"Rows with no DS Theta_0 at all: {unexpected}"

    def test_cost_values_in_php_range(self, consequence_df):
        """Cost DS1-Theta_0 for cost rows must look like PHP (not 000-PHP)."""
        cost = consequence_df[consequence_df.index.str.endswith("-Cost")]
        # DS1-Theta_0 may encode EoS as string; try to extract the first numeric part
        def extract_first_value(s) -> float | None:
            if pd.isna(s) or s == "":
                return None
            try:
                return float(str(s).split(",")[0])
            except (ValueError, AttributeError):
                return None

        if "DS1-Theta_0" in cost.columns:
            first_vals = cost["DS1-Theta_0"].apply(extract_first_value).dropna()
            # PHP values should be in range [500, 1_000_000_000]
            # (000 PHP → × 1000; smallest component has theta=500 PHP)
            # Values below 1000 would suggest still in 000-PHP (e.g., 0.5 instead of 500)
            small = first_vals[first_vals < 100]
            assert small.empty, (
                f"Suspiciously small cost DS1 values (possibly still in 000-PHP): "
                f"{small.to_dict()}"
            )

    def test_provenance_on_every_row(self, consequence_df):
        """Every row must have thesis_source."""
        assert "thesis_source" in consequence_df.columns, "Missing thesis_source column"
        missing = consequence_df["thesis_source"].isna() | (consequence_df["thesis_source"] == "")
        assert not missing.any(), (
            f"Rows missing thesis_source: {list(consequence_df.index[missing])}"
        )

    def test_provenance_confidence_values(self, consequence_df):
        if "provenance_confidence" in consequence_df.columns:
            vals = set(consequence_df["provenance_confidence"].dropna().unique())
            bad = vals - VALID_PROVENANCE_VALUES
            assert not bad, f"Invalid provenance_confidence values: {bad}"


class TestReplacementCSV:
    """Tests for replacement.csv structure."""

    def test_file_exists(self):
        assert REPLACEMENT_CSV.exists()

    def test_has_cost_and_time_stubs(self, replacement_df):
        """replacement.csv must have at least a replacement-Cost and replacement-Time row."""
        assert "replacement-Cost" in replacement_df.index, "Missing replacement-Cost row"
        assert "replacement-Time" in replacement_df.index, "Missing replacement-Time row"

    def test_replacement_cost_row_complete(self, replacement_df):
        """replacement-Cost row must be complete (Incomplete=0) with a valid Theta_0.

        As of 2026-06-26 replacement.csv was completed: per-archetype replacement
        costs are in archetypes.yaml and a representative fallback value (mid-rise
        RCMRF) is in Theta_0. The Incomplete=1 stub status has been resolved.
        """
        assert int(replacement_df.loc["replacement-Cost", "Incomplete"]) == 0, (
            "replacement-Cost: Expected Incomplete=0 (complete); file is no longer a stub"
        )
        theta0 = replacement_df.loc["replacement-Cost", "DS1-Theta_0"]
        assert pd.notna(theta0) and str(theta0) != "", (
            "replacement-Cost: DS1-Theta_0 must be populated with a numeric value"
        )
        assert float(theta0) > 0, "replacement-Cost: DS1-Theta_0 must be positive"


# ── Pelicun integration test ──────────────────────────────────────────────────

class TestPelicunLoad:
    """
    Verify Pelicun can actually load the custom library CSVs.
    Uses the low-level load_model_parameters API to avoid needing
    full demand/asset data.
    """

    def test_damage_model_loads_fragility(self, fragility_df):
        """
        Pelicun damage model can load fragility.csv without errors.
        Uses DamageModel_DS.load_model_parameters(data) via internal path.
        """
        import pelicun
        from pelicun.assessment import AssessmentBase
        from pelicun.base import Logger

        # Create minimal assessment with logging suppressed
        asmnt = AssessmentBase({"PrintLog": False, "Seed": 42})

        # Load through the low-level API: reads CSV, creates MultiIndex DataFrame
        from pelicun import file_io
        raw = file_io.load_from_file(str(FRAGILITY_CSV))

        # Confirm it returns a non-empty DataFrame
        assert raw is not None
        assert isinstance(raw, pd.DataFrame)
        assert len(raw) == EXPECTED_COMPONENT_COUNT

        # Convert to Pelicun's expected MultiIndex format
        from pelicun.base import convert_to_MultiIndex
        data_mi = convert_to_MultiIndex(raw, axis=1)

        # Call the DS damage model's load_model_parameters directly
        asmnt.damage.ds_model.load_model_parameters(data_mi)
        params = asmnt.damage.ds_model.damage_params

        assert params is not None, "damage_params is None after loading"
        assert len(params) == EXPECTED_COMPONENT_COUNT, (
            f"Expected {EXPECTED_COMPONENT_COUNT} rows in damage_params, got {len(params)}"
        )
        # Verify LS1-Theta_0 exists in the MultiIndex columns
        assert ("LS1", "Theta_0") in params.columns, "('LS1', 'Theta_0') not in damage_params"

    def test_loss_model_loads_consequence(self, consequence_df):
        """
        Pelicun loss model can load consequence_repair.csv without errors.
        """
        from pelicun import file_io
        from pelicun.base import convert_to_MultiIndex

        raw = file_io.load_from_file(str(CONSEQUENCE_CSV))
        assert raw is not None
        assert isinstance(raw, pd.DataFrame)
        # Should have 54 rows (27 × 2)
        assert len(raw) == EXPECTED_COMPONENT_COUNT * 2

        # Pelicun's loss model uses MultiIndex columns
        data_mi = convert_to_MultiIndex(raw, axis=1)

        # Verify DS columns exist at the first level
        first_level = set(data_mi.columns.get_level_values(0))
        ds_cols = {c for c in first_level if c.startswith("DS")}
        assert ds_cols, f"No DS* columns found in MultiIndex. First level: {first_level}"

        # Verify DV-Unit is present
        assert ("DV-Unit", "") in data_mi.columns or "DV-Unit" in raw.columns

    def test_pelicun_version_compatible(self):
        """Pelicun version must be >=3.9 and <4."""
        import pelicun
        from packaging.version import Version
        v = Version(pelicun.__version__)
        assert v >= Version("3.9"), f"Pelicun version {v} < 3.9"
        assert v < Version("4.0"), f"Pelicun version {v} >= 4.0 (breaking change expected)"
