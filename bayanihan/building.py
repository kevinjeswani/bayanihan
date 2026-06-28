"""Single-building seismic performance assessment using Pelicun."""
from __future__ import annotations

import importlib.resources as pkg_resources
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Residual-drift (irreparability) demolition fragility — FEMA P-58 (2018a) after
# Ramirez & Miranda (2012). A non-collapsed building is demolished (irreparable ->
# total loss) when its peak residual interstory drift ratio (RIDR) exceeds a lognormal
# demolition fragility:  P(demolition | RIDR) = Phi( ln(RIDR / median_ridr) / beta ).
#
# median_ridr is the per-archetype "Residual Drift Limit" from thesis Table 6-6
# (provenance: archetype_fragilities.yaml -> Building.metadata['residual_drift_limit_pct']);
# a 0.0% limit means residual drift is NOT a governing criterion (P_demo == 0). The
# dispersion beta is the FEMA P-58 default (0.30); the thesis tabulates only the median.
# Parameters live in data/demolition_fragility.json (never hardcoded in Python).
# See docs/learnings/2026-06-27_rdr_demolition.md.
# ---------------------------------------------------------------------------
_DEMOLITION_PARAMS_FILE = "demolition_fragility.json"


@lru_cache(maxsize=1)
def _demolition_params() -> dict:
    """Load {beta_demolition, default_median_ridr_pct} from demolition_fragility.json.

    Falls back to the FEMA P-58 default (beta=0.30, median=1.0%) if the file is absent.
    """
    try:
        with open(_get_data_path(_DEMOLITION_PARAMS_FILE), encoding="utf-8") as fh:
            d = json.load(fh)
        return {
            "beta_demolition": float(d.get("beta_demolition", 0.30)),
            "default_median_ridr_pct": float(d.get("default_median_ridr_pct", 1.0)),
        }
    except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
        log.warning("demolition_fragility.json not loadable (%s); using FEMA P-58 default.", exc)
        return {"beta_demolition": 0.30, "default_median_ridr_pct": 1.0}


def demolition_probability(ridr: np.ndarray, median_ridr_pct: float) -> np.ndarray:
    """P(demolition | RIDR) from the lognormal residual-drift demolition fragility.

    Args:
        ridr: residual interstory drift ratio(s), unitless (e.g. 0.013 = 1.3%).
        median_ridr_pct: median RIDR demolition threshold in PERCENT (thesis Table 6-6
            "Residual Drift Limit", e.g. 1.0). A value <= 0 means residual drift is NOT a
            governing criterion for this archetype -> probability 0 everywhere.

    Returns:
        Array of demolition probabilities in [0, 1], same shape as ``ridr``.
    """
    ridr = np.asarray(ridr, dtype=float)
    median = float(median_ridr_pct) / 100.0  # percent -> unitless ratio
    if median <= 0.0:
        return np.zeros_like(ridr)
    beta = _demolition_params()["beta_demolition"]
    safe = np.clip(ridr, 1e-12, None)
    return norm.cdf(np.log(safe / median) / beta)


def sample_demolition(
    ridr: np.ndarray,
    median_ridr_pct: float,
    collapse_mask: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Bernoulli demolition mask for NON-collapsed realizations.

    A realization is demolished iff it did not collapse AND a Bernoulli(P(demo|RIDR))
    draw succeeds. Collapsed realizations are already total loss (handled separately) and
    are never additionally flagged here, so the collapse / demolition / component-repair
    routing is mutually exclusive (order: collapse -> else demolition -> else component).

    Args:
        ridr: (n,) per-realization peak residual interstory drift ratio (unitless).
        median_ridr_pct: per-archetype median RIDR demolition threshold (percent).
        collapse_mask: (n,) bool — realizations already routed to collapse->replacement.
        rng: seeded RNG.

    Returns:
        (n,) bool demolition mask (True where the building is demolished, non-collapsed).
    """
    ridr = np.asarray(ridr, dtype=float)
    collapse_mask = np.asarray(collapse_mask, dtype=bool)
    p_demo = demolition_probability(ridr, median_ridr_pct)
    draws = rng.random(ridr.shape[0]) < p_demo
    return draws & ~collapse_mask


# ---------------------------------------------------------------------------
# Fallback component inventory — used ONLY when an archetype has no row in the
# packaged per-archetype table (component_quantities.csv). Real per-archetype
# FEMA P-58 populations now come from that table (thesis Table D-13, p.311);
# see _load_component_table / _build_cmp_marginals below. This fallback keeps a
# single archetype runnable even with no provenanced data (e.g. a brand-new
# archetype id), and is intentionally generic (ductile RC frame + CHB + ceiling).
# Quantities are per-story (applied to every story via Location='all').
# ---------------------------------------------------------------------------
_DEFAULT_CMP_INVENTORY: dict[str, dict] = {
    # Ductile RCMRF beam-column joints — 1-sided (exterior bays) at every story
    "PH.S.DRCMRF.1S": {"units": "1 EA", "quantity": 2, "directions": "1"},
    # Ductile RCMRF beam-column joints — 2-sided (interior bays)
    "PH.S.DRCMRF.2S": {"units": "1 EA", "quantity": 4, "directions": "1"},
    # CHB infill — solid, unreinforced (125 SF panels)
    "PH.NS.CHB.SU": {"units": "125 SF", "quantity": 2, "directions": "1"},
    # CHB infill — perforated/with openings (125 SF panels) — Repair Class 2 driver
    "PH.NS.CHB.PU": {"units": "125 SF", "quantity": 1, "directions": "1"},
    # Suspended ceiling — non-seismic (250 SF zones); acceleration (Direction 0)
    "PH.NS.CLG.NS": {"units": "250 SF", "quantity": 2, "directions": "0"},
    # Ceiling fixtures — non-seismic (Repair Class 3 driver); acceleration
    "PH.NS.FIX.NS": {"units": "1 EA", "quantity": 4, "directions": "0"},
}

#: Packaged per-archetype component-quantity table (long format).
_COMPONENT_TABLE_FILE = "component_quantities.csv"

# ---------------------------------------------------------------------------
# Non-structural mitigation (the thesis's SECOND mitigation layer) — a
# component-level fragility/consequence swap that upgrades acceleration-/drift-
# sensitive non-structural components to their anchored/braced/seismic
# counterparts (Jeswani 2021 Table 6-3, p.128; Ch 8.3). Its purpose is to reduce
# INJURIES from falling hazards: the upgraded counterparts (PH.NS.CLG.BR,
# PH.NS.FIX.SE, PH.NS.CHB.SR/PR) carry no non-collapse injury consequence or a far
# higher capacity, and electronics (PH.NS.ELEC.DT/WM) are REMOVED from the
# mitigated models ("simulate no damage/casualty"). This is NOT new EDPs and NOT a
# structural re-analysis (HARD SCOPE) — only the Pelicun component marginals change,
# which then flows into the damage sample, the component repair loss, and the
# non-collapse component injury pathway (casualties.py). It does NOT change collapse
# probability — that is the separate structural-FRP layer's job
# (portfolio.MITIGATION_RETROFIT_MAP). The map lives in
# data/nonstructural_mitigation.json (never hardcoded in Python).
# ---------------------------------------------------------------------------
_NS_MITIGATION_FILE = "nonstructural_mitigation.json"


@lru_cache(maxsize=1)
def _ns_mitigation_map() -> tuple[dict[str, str], frozenset[str]]:
    """Load the non-structural mitigation component map.

    Returns:
        ``(substitutions, removed)`` where ``substitutions`` maps a base component
        id to its upgraded (anchored/braced/seismic) counterpart id, and ``removed``
        is the set of component ids dropped entirely from the mitigated marginals
        (the thesis's "removed item from mitigated models" — electronics). Returns
        ``({}, frozenset())`` if the file is somehow absent (mitigation then a no-op).
    """
    try:
        with open(_get_data_path(_NS_MITIGATION_FILE), encoding="utf-8") as fh:
            d = json.load(fh)
        subs = {
            str(k): str(v["to"])
            for k, v in d.get("substitutions", {}).items()
            if isinstance(v, dict) and v.get("to")
        }
        removed = frozenset(str(k) for k in d.get("removed", {}))
        return subs, removed
    except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
        log.warning(
            "nonstructural_mitigation.json not loadable (%s); NS mitigation is a no-op.", exc
        )
        return {}, frozenset()


@lru_cache(maxsize=1)
def _load_component_table() -> pd.DataFrame:
    """Load the packaged per-archetype FEMA P-58 component-quantity table.

    Source: ``bayanihan/data/component_quantities.csv`` (generated from
    thesis Table D-13 via ``utils/build_component_quantities_csv.py``; every
    ``component_id`` resolves in fragility.csv + consequence_repair.csv).

    Returns:
        DataFrame with columns ``archetype, story, component_id, quantity, units,
        direction, thesis_source, provenance_confidence``. Empty DataFrame (with the
        right columns) if the file is somehow absent — callers then fall back to
        ``_DEFAULT_CMP_INVENTORY``.
    """
    cols = [
        "archetype", "story", "component_id", "quantity",
        "units", "direction", "thesis_source", "provenance_confidence",
    ]
    try:
        path = _get_data_path(_COMPONENT_TABLE_FILE)
        df = pd.read_csv(path)
        df["direction"] = df["direction"].astype(str)
        return df
    except (FileNotFoundError, OSError, ValueError) as exc:
        log.warning("component_quantities.csv not loadable (%s); using fallback.", exc)
        return pd.DataFrame(columns=cols)


@lru_cache(maxsize=1)
def _merged_archetype_map() -> dict[str, str]:
    """Return {archetype_id: parent_archetype_id} for merged archetypes.

    Merged archetypes (e.g. ``C4-M (Mid)`` -> ``C1-M (Hi)``) have no independently
    tabulated component population in Table D-13; they reuse their parent's. The
    parent is read from ``docs/thesis/data/component_quantities.yaml`` (``merged_into``),
    so this stays in sync with the provenance source. Returns ``{}`` on any failure
    (callers then treat unknown archetypes via the fallback inventory).
    """
    try:
        import yaml

        # The YAML lives under docs/thesis/data; resolve via the repo root.
        pkg_dir = Path(str(pkg_resources.files("bayanihan")))
        yaml_path = pkg_dir.parent / "docs" / "thesis" / "data" / "component_quantities.yaml"
        if not yaml_path.is_file():
            return {}
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        out: dict[str, str] = {}
        for arch, info in data.get("component_quantities", {}).items():
            parent = info.get("merged_into")
            if parent:
                out[arch] = parent
        return out
    except Exception as exc:  # noqa: BLE001 — provenance optional; degrade gracefully
        log.debug("merged-archetype map unavailable (%s).", exc)
        return {}


def _resolve_component_archetype(archetype_id: str) -> str:
    """Resolve an archetype id to the id whose component population should be used.

    Follows the ``merged_into`` chain (component_quantities.yaml) so merged
    archetypes inherit their parent's Table D-13 population.
    """
    seen = set()
    cur = archetype_id
    merged = _merged_archetype_map()
    while cur in merged and cur not in seen:
        seen.add(cur)
        cur = merged[cur]
    return cur


def _build_cmp_marginals(
    stories: int, archetype_id: str, nonstructural_mitigated: bool = False
) -> pd.DataFrame:
    """Build the Pelicun component-marginals DataFrame for an archetype.

    Loads the archetype's REAL FEMA P-58 component population (thesis Table D-13)
    from the packaged ``component_quantities.csv`` and emits one marginal row per
    (component_id, story, direction). Story quantities are placed at their specific
    ``Location`` (1..N); a per-story quantity at story ``s`` greater than the
    building's ``stories`` is dropped (the EDP demand only spans 1..stories).

    Falls back to ``_DEFAULT_CMP_INVENTORY`` (placed at every story via
    Location='all') only when the archetype (after merge resolution) has no rows
    in the table.

    Args:
        stories: building height (number of stories).
        archetype_id: archetype id whose component population to use.
        nonstructural_mitigated: when True, apply the thesis's non-structural
            mitigation (Table 6-3) as a component swap on the marginals — upgrade
            ceilings/fixtures/CHB to their anchored/braced/seismic counterparts and
            REMOVE electronics. See :func:`_ns_mitigation_map`. Quantities,
            locations and directions are preserved; only the component id (or its
            presence) changes. This is the data-level realisation of the
            non-structural injury-reduction layer; it flows into the damage sample,
            the component repair loss, and the casualty injury pathway.

    Returns:
        DataFrame indexed by component id with columns Units, Location, Direction,
        Family, Theta_0, Theta_1 — compatible with ``pelicun.asset.load_cmp_model``.
        Note the index may repeat a component id across different Location/Direction
        rows (Pelicun supports duplicate-index marginals).
    """
    table = _load_component_table()
    resolved = _resolve_component_archetype(archetype_id)
    sub = table[table["archetype"] == resolved] if not table.empty else table

    subs, removed = _ns_mitigation_map() if nonstructural_mitigated else ({}, frozenset())

    records = []
    index = []

    if sub is not None and not sub.empty:
        for r in sub.itertuples(index=False):
            st = int(r.story)
            if st < 1 or st > stories:
                # Component sits on a story the building/EDP sample does not cover.
                # (e.g. penthouse on a building modelled with fewer EDP stories.)
                continue
            cmp_id = str(r.component_id)
            if nonstructural_mitigated:
                if cmp_id in removed:
                    continue  # electronics: removed from mitigated models entirely
                cmp_id = subs.get(cmp_id, cmp_id)  # swap to anchored/braced counterpart
            records.append({
                "Units": str(r.units),
                "Location": str(st),
                "Direction": str(r.direction),
                "Family": float("nan"),
                "Theta_0": float(r.quantity),
                "Theta_1": float("nan"),
            })
            index.append(cmp_id)

    if not records and not (sub is not None and not sub.empty):
        # Fallback: generic inventory at every story (Location='all'). Only used when
        # the archetype has NO rows in the table (not merely when mitigation removed
        # rows — a fully-removed set is a legitimate, if degenerate, mitigated model).
        for cmp_id, info in _DEFAULT_CMP_INVENTORY.items():
            if nonstructural_mitigated:
                if cmp_id in removed:
                    continue
                cmp_id = subs.get(cmp_id, cmp_id)
            records.append({
                "Units": info["units"],
                "Location": "all",
                "Direction": str(info.get("directions", "1")),
                "Family": float("nan"),
                "Theta_0": float(info["quantity"]),
                "Theta_1": float("nan"),
            })
            index.append(cmp_id)

    df = pd.DataFrame(records, index=pd.Index(index, name=""))
    return df


def _build_demand_df(edp_samples: np.ndarray, stories: int) -> pd.DataFrame:
    """Convert (n_sims, n_stories, 2) EDP array into Pelicun demand DataFrame.

    The input array has shape (n_simulations, n_stories, n_edp_types) where
    edp_types[0] = PID (interstory drift ratio, unitless) and
    edp_types[1] = PFA (floor acceleration, g).

    Column naming convention follows Pelicun demands format:
        PID-{story}-{direction}  →  unitless
        PFA-{story}-{direction}  →  g

    Floor 0 = ground, Floor 1 = first story above grade, etc.
    PID is assigned to the story it spans (1 to N).
    PFA is assigned to the floor level (1 to N+1 inclusive; here we use 1..N).

    Args:
        edp_samples: Shape (n_sims, n_stories, 2).
        stories: Number of stories in the building.

    Returns:
        DataFrame with row index = simulation index (int) plus a 'Units' row.
    """
    n_sims, n_stories_data, n_types = edp_samples.shape

    columns = []
    data_cols = {}

    # PID columns — stories 1..stories (building height), direction 1
    # If edp_samples has fewer stories than the building, repeat the last available
    # story's values for the missing floors (conservative approximation).
    for s in range(1, stories + 1):
        col = f"PID-{s}-1"
        columns.append(col)
        src_s = min(s, n_stories_data) - 1  # clamp to available data
        data_cols[col] = edp_samples[:, src_s, 0]

    # PFA columns — stories 1..stories, direction 1
    for s in range(1, stories + 1):
        col = f"PFA-{s}-1"
        columns.append(col)
        src_s = min(s, n_stories_data) - 1
        data_cols[col] = edp_samples[:, src_s, 1]

    df = pd.DataFrame(data_cols, index=range(1, n_sims + 1))
    df.index.name = None

    # Append Units row
    units_row = pd.DataFrame(
        {col: ["unitless" if col.startswith("PID") else "g"] for col in columns},
        index=["Units"],
    )
    df = pd.concat([df, units_row])
    return df


def _get_data_path(filename: str) -> str:
    """Return absolute path to a bundled data file via importlib.resources."""
    ref = pkg_resources.files("bayanihan").joinpath(f"data/{filename}")
    # In Python 3.9+ we can use as_posix() on a Traversable path
    # For files that must be opened as a real path, we need str(ref)
    return str(ref)


@dataclass
class Building:
    """Represents a single building for PBEE assessment.

    Parameters sourced from docs/thesis/data/*.yaml — see provenance fields there.
    """

    archetype: str
    stories: int
    year_built: int
    site_class: str
    lat: float
    lon: float
    metadata: dict = field(default_factory=dict)
    #: When True, build the Pelicun component model with the thesis's non-structural
    #: mitigation applied (Table 6-3 component swap: braced ceilings, seismic/safety-
    #: wired fixtures, reinforced CHB, electronics removed). Affects the damage sample,
    #: the component repair loss, and the non-collapse component injury pathway. Set on
    #: the building for the mitigated portfolio run; default False (existing/base case).
    nonstructural_mitigated: bool = False

    @classmethod
    def from_archetype(cls, archetype_id: str, **overrides) -> Building:
        """Instantiate a building from one of the 20 thesis archetypes.

        Args:
            archetype_id: One of the 20 archetype IDs (see archetypes.py).
            **overrides: Optional attribute overrides (e.g., lat, lon for
                portfolio use, year_built, site_class).

        Raises:
            ValueError: If archetype_id is not recognized.
        """
        # Import here to avoid circular import (archetypes → building → archetypes)
        from bayanihan.archetypes import get_archetype
        return get_archetype(archetype_id, **overrides)

    def assess(
        self,
        edp_samples: np.ndarray,
        seed: int | None = None,
    ) -> dict:
        """Run Pelicun damage + loss + recovery assessment.

        Uses the custom component DB in bayanihan/data/ via
        Pelicun's load_model_parameters.

        This is the low-level path: the caller supplies the demand sample directly.
        For real multi-stripe EDPs at a scenario Sa, prefer :meth:`assess_scenario`,
        which builds the demand sample (and collapse mask) from the bundled EDP store
        via :mod:`bayanihan.edp` and then calls this method.

        Args:
            edp_samples: EDP sample array. Shape (n_simulations, n_stories,
                n_edp_types) where edp_types = [PID (unitless), PFA (g)].
            seed: Random seed for reproducibility.

        Returns:
            dict with keys:
                - damage: dict mapping component ID to damage state array (n_sims,)
                - loss_ratio: (n_simulations,) repair cost as fraction of replacement
                - repair_cost: (n_simulations,) repair cost in PHP_2020
                - repair_time: (n_simulations,) sequential repair time in worker_hours
                - reoccupancy_days: (n_simulations,) from recovery.py (None if stub)
                - functional_recovery_days: (n_simulations,) from recovery.py (None if stub)
                - full_recovery_days: (n_simulations,) from recovery.py (None if stub)
        """

        # Silence Pelicun's verbose logging during testing
        pelicun_logger = logging.getLogger("pelicun")
        prev_level = pelicun_logger.level
        pelicun_logger.setLevel(logging.WARNING)

        try:
            return self._run_pelicun(edp_samples, seed)
        finally:
            pelicun_logger.setLevel(prev_level)

    def assess_scenario(
        self,
        sa_t1: float,
        soil_bin: str | None = None,
        n_realizations: int = 1000,
        seed: int | None = None,
    ) -> dict:
        """Assess this building from REAL multi-stripe EDPs at a scenario ``Sa(T_avg)``.

        Builds a Pelicun-ready conditional demand sample from the bundled EDP store
        (``bayanihan.edp.demand_for``), runs the Pelicun damage->loss->recovery
        pipeline on the non-collapsed realizations, and overrides collapsed realizations
        to total loss (loss_ratio = 1, repair_cost = replacement_cost, repair_time =
        replacement_time). See ``docs/learnings/2026-06-26_edp_ingestion_design.md``.

        Args:
            sa_t1: scenario spectral acceleration Sa(T_avg) in g.
            soil_bin: soil bin (``"C1"``, ``"C2"``, ``"D"``, ``"C"``). Defaults from the
                building's ``site_class`` (D->"D", C->"C"/"C1"), then falls back within
                the archetype's available bins.
            n_realizations: number of Monte-Carlo realizations.
            seed: RNG seed for reproducibility.

        Returns:
            Same dict as :meth:`assess`, plus:
                - p_collapse: scalar P(collapse | Sa)
                - collapse_mask: (n_realizations,) bool
                - demolition_mask: (n_realizations,) bool — non-collapsed buildings
                  demolished by the residual-drift trigger (total loss)
                - p_demolition: scalar mean P(demolition | RIDR) over realizations
                - edp_archetype / edp_soil_bin: the dataset actually used
        """
        from bayanihan import edp as _edp

        if soil_bin is None:
            soil_bin = self._default_soil_bin()

        sample = _edp.demand_for(
            archetype=self.archetype,
            soil_bin=soil_bin,
            sa_t1=sa_t1,
            n_realizations=n_realizations,
            seed=seed,
        )

        # Run the standard Pelicun pipeline on the full demand sample.
        result = self.assess(sample.edp, seed=seed)

        # --- Residual-drift demolition (FEMA P-58 §7.6 / Ramirez & Miranda 2012) ----
        # MEDIAN peak RIDR at the scenario Sa (capped at the top calibrated stripe —
        # collapse governs above it), through the lognormal demolition fragility
        # (median = Table 6-6 RIDR limit, beta=0.30), then Bernoulli among NON-collapsed
        # realizations. Order: collapse -> demolition. The residual EDP's record-to-record
        # scatter is NOT additionally sampled (the beta=0.30 fragility already carries the
        # threshold uncertainty); sampling it too double-counted the residual variability
        # and over-fired ductiles. See docs/learnings/2026-06-27_demolition_recalibration.md.
        collapse_mask = sample.collapse_mask
        ridr = _edp.median_residual_drift_for_sa_field(
            sample.archetype, sample.soil_bin,
            np.full(int(n_realizations), float(sa_t1)),
        )
        demo_rng = np.random.default_rng(None if seed is None else seed + 104729)
        median_ridr_pct = self._get_residual_drift_limit_pct()
        demolition_mask = sample_demolition(
            ridr, median_ridr_pct, collapse_mask, demo_rng
        )

        # Total-loss override: collapse OR demolition -> replacement cost + time.
        total_loss_mask = collapse_mask | demolition_mask
        if total_loss_mask.any():
            repl_cost = self._get_replacement_cost()
            repl_time_wh = self._get_replacement_time_wh()

            result["repair_cost"] = np.where(total_loss_mask, repl_cost, result["repair_cost"])
            result["repair_time"] = np.where(total_loss_mask, repl_time_wh, result["repair_time"])
            if repl_cost > 0:
                result["loss_ratio"] = np.where(total_loss_mask, 1.0, result["loss_ratio"])

            # Recovery: total-loss buildings take the full replacement duration.
            repl_days = repl_time_wh / 8.0  # WORKERS_PER_DAY_DEFAULT
            for key in (
                "reoccupancy_days",
                "functional_recovery_days",
                "full_recovery_days",
            ):
                arr = result.get(key)
                if arr is not None:
                    result[key] = np.where(total_loss_mask, repl_days, arr)

        result["p_collapse"] = sample.p_collapse
        result["collapse_mask"] = collapse_mask
        result["demolition_mask"] = demolition_mask
        result["p_demolition"] = float(
            demolition_probability(ridr, median_ridr_pct).mean()
        )
        result["edp_archetype"] = sample.archetype
        result["edp_soil_bin"] = sample.soil_bin

        # --- FEMA P-58 casualties (injuries + fatalities) -----------------------------
        # Non-collapse component-driven injuries (affected-area model) on non-collapsed
        # realizations + collapse-driven injuries/fatalities (HAZUS-typology rates). Scaled
        # by the building's population. Population/floor area come from metadata (set by the
        # archetype loader or the inventory); skipped silently if population is unknown.
        self._attach_casualties(result, collapse_mask)
        return result

    def _attach_casualties(self, result: dict, collapse_mask: np.ndarray) -> None:
        """Compute injuries + fatalities for this building and attach to ``result``.

        Uses :mod:`bayanihan.casualties` (FEMA P-58 model). Reads ``population``
        and ``floor_area_m2`` from ``self.metadata``. If population is missing/zero the
        casualty arrays are zeros (no exposure assumed) — the caller can detect this via
        ``result['casualty_population']``.
        """
        try:
            from bayanihan import casualties as _cas
        except ImportError as exc:  # pragma: no cover - casualties module is committed
            log.debug("casualties module unavailable (%s).", exc)
            return

        population = float(self.metadata.get("population", 0.0) or 0.0)
        floor_area_m2 = float(self.metadata.get("floor_area_m2", 0.0) or 0.0)
        cas = _cas.building_casualties(
            damage_sample=result.get("damage_sample"),
            collapse_mask=np.asarray(collapse_mask, dtype=bool),
            archetype=self.archetype,
            population=population,
            floor_area_m2=floor_area_m2,
        )
        result["injuries"] = cas["injuries"]
        result["fatalities"] = cas["fatalities"]
        result["injuries_noncollapse"] = cas["injuries_noncollapse"]
        result["injuries_collapse"] = cas["injuries_collapse"]
        result["fatalities_noncollapse"] = cas["fatalities_noncollapse"]
        result["fatalities_collapse"] = cas["fatalities_collapse"]
        result["casualty_population"] = population

    def _get_residual_drift_limit_pct(self) -> float:
        """Return this archetype's median RIDR demolition threshold (percent).

        Source: thesis Table 6-6 "Residual Drift Limit", carried on the archetype as
        ``metadata['residual_drift_limit_pct']`` (set by archetypes.get_archetype from
        archetype_fragilities.yaml). A value of 0.0 means residual drift is NOT a
        governing criterion for this archetype (no demolition fragility). If the
        metadata key is missing (e.g. a hand-built Building), fall back to the
        FEMA P-58 default median (data/demolition_fragility.json).
        """
        v = self.metadata.get("residual_drift_limit_pct")
        if v is None:
            return float(_demolition_params()["default_median_ridr_pct"])
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(_demolition_params()["default_median_ridr_pct"])

    def _default_soil_bin(self) -> str:
        """Map the building's site_class to an EDP soil bin (best effort)."""
        sc = (self.site_class or "").strip().upper()
        # Native EDP bins: C1, C2, D, C. Site classes are typically C / D.
        if sc.startswith("D"):
            return "D"
        if sc.startswith("C"):
            return "C"  # edp._resolve_dataset falls back to C1/C2 if 'C' absent
        return "D"

    def _get_replacement_time_wh(self) -> float:
        """Return replacement time (worker_hours) for the collapse->replacement path."""
        arch_time = self.metadata.get("replacement_time_worker_hours")
        if arch_time:
            return float(arch_time)
        # Convert an archetype replacement_time in calendar days if present.
        arch_days = self.metadata.get("replacement_time_days")
        if arch_days:
            return float(arch_days) * 8.0  # 8 workers/day * hours... (worker_hours/day=8)
        try:
            repl_path = _get_data_path("replacement.csv")
            repl_df = pd.read_csv(repl_path, index_col=0)
            if "replacement-Time" in repl_df.index:
                theta0 = repl_df.loc["replacement-Time", "DS1-Theta_0"]
                if pd.notna(theta0) and str(theta0) != "":
                    return float(theta0)
        except Exception:
            pass
        return 52560.0  # replacement.csv default fallback

    def _run_pelicun(
        self,
        edp_samples: np.ndarray,
        seed: int | None = None,
    ) -> dict:
        """Internal: run the Pelicun pipeline."""
        from pelicun.assessment import Assessment

        n_sims = edp_samples.shape[0]

        # ------------------------------------------------------------------
        # 1. Initialise assessment
        # ------------------------------------------------------------------
        asmnt = Assessment(
            {"PrintLog": False, "Seed": seed if seed is not None else 42}
        )
        # Register custom units not in Pelicun's default list:
        #   PHP_2020 — Philippine Peso reference year 2020 (no conversion needed;
        #              factor=1 means values are kept as-is)
        #   worker_hour — labour time in hours (factor=1)
        asmnt.unit_conversion_factors["PHP_2020"] = 1.0
        asmnt.unit_conversion_factors["worker_hour"] = 1.0

        # ------------------------------------------------------------------
        # 2. Build demand DataFrame and load sample
        # ------------------------------------------------------------------
        demand_df = _build_demand_df(edp_samples, self.stories)
        asmnt.demand.load_sample(demand_df)
        # Use empirical distribution — preserve the provided sample as-is
        asmnt.demand.calibrate_model({"ALL": {"DistributionFamily": "empirical"}})
        asmnt.demand.generate_sample(
            {"SampleSize": n_sims, "PreserveRawOrder": True}
        )

        # ------------------------------------------------------------------
        # 3. Asset model — component inventory
        # ------------------------------------------------------------------
        asmnt.stories = self.stories
        cmp_marginals = _build_cmp_marginals(
            self.stories, self.archetype, self.nonstructural_mitigated
        )
        asmnt.asset.load_cmp_model({"marginals": cmp_marginals})
        asmnt.asset.generate_cmp_sample()

        # ------------------------------------------------------------------
        # 4. Damage model — load custom fragility DB
        # ------------------------------------------------------------------
        frag_path = _get_data_path("fragility.csv")
        cmp_set = set(asmnt.asset.list_unique_component_ids())
        asmnt.damage.load_model_parameters([frag_path], cmp_set)
        asmnt.damage.calculate()

        # ------------------------------------------------------------------
        # 5. Loss model — load custom consequence DB
        # ------------------------------------------------------------------
        cons_path = _get_data_path("consequence_repair.csv")

        asmnt.loss.decision_variables = ("Cost", "Time")

        # Build a simple loss map: each component damage maps to repair consequence.
        # Pelicun 3.9 API: Driver column without "DMG-" prefix; "Repair" column
        # (not the deprecated "BldgRepair").
        damage_cmp_ids = list(asmnt.asset.list_unique_component_ids())
        loss_map_rows = []
        for cmp_id in damage_cmp_ids:
            loss_map_rows.append({
                "Driver": cmp_id,
                "Repair": cmp_id,
            })
        loss_map_df = pd.DataFrame(loss_map_rows).set_index("Driver")

        asmnt.loss.add_loss_map(loss_map_df, loss_map_policy="fill")
        # Load component repair consequences only (not replacement.csv — that is
        # handled separately via aggregate_loss(replacement_configuration)).
        asmnt.loss.load_model_parameters([cons_path])
        asmnt.loss.calculate()

        # ------------------------------------------------------------------
        # 6. Aggregate losses
        # ------------------------------------------------------------------
        # Aggregate without replacement configuration for now.
        # The replacement.csv placeholder (Incomplete=1) doesn't have a Theta_0,
        # so we can't build a valid RV. Replacement triggering can be added in P5
        # once per-archetype replacement costs are populated.
        #
        # Degenerate zero-loss guard: when EVERY realization is below the damage
        # threshold (a legitimately undamaged building — e.g. a low-vulnerability
        # archetype under a far-field / low-Sa scenario with a small sample),
        # Pelicun's aggregate_loss has nothing to aggregate and raises internally
        # (assert isinstance(output, tuple) in assessment.aggregate_loss). The
        # physically-correct outcome is zero repair cost/time, so we treat that
        # specific case as agg_loss = None and fall through to the zero defaults
        # below. This never triggers at the calibrated WVF-7.3 N=1000 (always some
        # damage); it only makes the low-intensity scenarios robust at small N.
        try:
            agg_loss, _ = asmnt.aggregate_loss(replacement_configuration=None)
        except AssertionError:
            agg_loss = None

        # ------------------------------------------------------------------
        # 7. Extract results
        # ------------------------------------------------------------------
        # Damage sample: dict of {cmp_id: array of DS indices}
        dmg_sample = asmnt.damage.sample
        damage_dict: dict[str, np.ndarray] = {}
        if dmg_sample is not None:
            for cmp_col in dmg_sample.columns.get_level_values(0).unique():
                try:
                    col_data = dmg_sample[cmp_col]
                    if hasattr(col_data, "values"):
                        damage_dict[str(cmp_col)] = col_data.values.flatten()
                except Exception:
                    pass

        # Keep the raw Pelicun damage sample (MultiIndex cmp/loc/dir/uid/ds) so the
        # FEMA P-58 casualty model (casualties.py) can read per-component, per-DS damaged
        # quantities for the non-collapse affected-area injury/fatality computation.
        damage_sample_raw = dmg_sample

        # Cost and time from aggregated losses.
        # Pelicun 3.9 returns a MultiIndex DataFrame with columns like:
        #   ('repair_cost', '')  and  ('repair_time', 'sequential')
        repair_cost = np.zeros(n_sims)
        repair_time = np.zeros(n_sims)

        if agg_loss is not None and not agg_loss.empty:
            cols = agg_loss.columns
            # Find repair cost column (level-0 = 'repair_cost')
            for col in cols:
                col_key = col[0] if isinstance(col, tuple) else col
                if "repair_cost" in str(col_key).lower() or col_key == "Cost":
                    cost_vals = agg_loss[col].values
                    repair_cost = np.nan_to_num(cost_vals.astype(float), nan=0.0)
                    break
            # Find sequential repair time column
            for col in cols:
                col_l0 = col[0] if isinstance(col, tuple) else col
                col_l1 = col[1] if isinstance(col, tuple) and len(col) > 1 else ""
                if "repair_time" in str(col_l0).lower() or col_l0 == "Time":
                    if "sequential" in str(col_l1).lower() or col_l1 == "":
                        time_vals = agg_loss[col].values
                        repair_time = np.nan_to_num(time_vals.astype(float), nan=0.0)
                        break

        # Replacement cost for loss ratio computation
        replacement_cost = self._get_replacement_cost()
        if replacement_cost > 0:
            loss_ratio = np.clip(repair_cost / replacement_cost, 0.0, 1.0)
        else:
            loss_ratio = np.zeros(n_sims)

        # ------------------------------------------------------------------
        # 8. Recovery — per-repair-class milestone computation
        # ------------------------------------------------------------------
        # Extract per-component repair time from Pelicun loss sample.
        # Pelicun provides repair time in worker_hours per component; recovery.py
        # maps components to repair classes (from redi_impedance_factors.yaml Table D-16)
        # and aggregates to per-class calendar days.
        #
        # See docs/reference/pelicun_recovery_notes.md for the full Pelicun capability
        # audit confirming this is the correct access path.
        reoccupancy_days = None
        functional_recovery_days = None
        full_recovery_days = None

        try:
            import bayanihan.recovery as _recovery

            # --- Extract per-component repair time from Pelicun loss sample ---
            # loss.sample columns: ['dv', 'loss', 'dmg', 'ds', 'loc', 'dir', 'uid']
            # Aggregate over ds/loc/dir/uid → (n_sims, n_components) in worker_hours
            time_per_cmp: pd.DataFrame | None = None
            if asmnt.loss.sample is not None:
                loss_sample = asmnt.loss.sample
                dv_level = loss_sample.columns.names[0] if loss_sample.columns.names else 'dv'
                if 'Time' in loss_sample.columns.get_level_values(dv_level):
                    time_raw = loss_sample.xs('Time', level=dv_level, axis=1)
                    # Group by 'loss' level (component ID), sum over all other levels
                    loss_level = time_raw.columns.names[0] if time_raw.columns.names else 'loss'
                    time_per_cmp = time_raw.T.groupby(level=loss_level).sum().T

            # --- Damage state proxy: any repair time → DS>0 ---
            # Use repair_time > 0 as the indicator (loss_ratio may be 0 when
            # replacement_cost is unknown/zero, but repair_time is always > 0
            # when any component is damaged).
            # Binary (0 or 1) is sufficient to trigger impeding factors.
            ds_proxy = np.where(repair_time > 0.0, 1, 0).astype(int)

            has_comp_recovery = hasattr(_recovery, "compute_recovery_from_components")
            if time_per_cmp is not None and not time_per_cmp.empty and has_comp_recovery:
                # Primary path: per-component repair time → per-class milestones
                recovery_result = _recovery.compute_recovery_from_components(
                    time_per_cmp=time_per_cmp,
                    damage_state=ds_proxy,
                    seed=seed,
                )
            elif hasattr(_recovery, "compute_recovery"):
                # Fallback: aggregate repair time (worker_hours) → scalar interface
                repair_days = repair_time / _recovery.WORKERS_PER_DAY_DEFAULT
                recovery_result = _recovery.compute_recovery(
                    repair_time_samples=repair_days,
                    damage_state=ds_proxy,
                    seed=seed,
                )
            else:
                recovery_result = {}

            reoccupancy_days = recovery_result.get("reoccupancy_days")
            functional_recovery_days = recovery_result.get("functional_recovery_days")
            full_recovery_days = recovery_result.get("full_recovery_days")

        except (ImportError, NotImplementedError, AttributeError) as exc:
            log.debug(
                "recovery not available (%s); recovery keys set to None.",
                exc,
            )

        return {
            "damage": damage_dict,
            "damage_sample": damage_sample_raw,
            "loss_ratio": loss_ratio,
            "repair_cost": repair_cost,
            "repair_time": repair_time,
            "reoccupancy_days": reoccupancy_days,
            "functional_recovery_days": functional_recovery_days,
            "full_recovery_days": full_recovery_days,
        }

    def _build_replacement_config(self, repl_path: str):
        """Build Pelicun replacement_configuration tuple from replacement.csv."""
        try:
            from pelicun import uq

            repl_df = pd.read_csv(repl_path, index_col=0)
            cost_row = (
                repl_df.loc["replacement-Cost"] if "replacement-Cost" in repl_df.index else None
            )
            time_row = (
                repl_df.loc["replacement-Time"] if "replacement-Time" in repl_df.index else None
            )

            rv_reg = uq.RandomVariableRegistry(asmnt=None)

            if cost_row is not None:
                theta0 = cost_row.get("DS1-Theta_0", None)
                theta1 = cost_row.get("DS1-Theta_1", 0.35)
                if pd.notna(theta0) and theta0 != "":
                    # Use archetype replacement cost if available in metadata
                    arch_cost = self.metadata.get("replacement_cost_PHP")
                    median = float(arch_cost) if arch_cost else float(theta0)
                    rv_reg.add_RV(
                        uq.rv_class_map("normal")(
                            name="replacement-Cost",
                            theta=[median, float(theta1) if pd.notna(theta1) else 0.35],
                            truncation_limits=[0.0, None],
                        )
                    )

            if time_row is not None:
                theta0 = time_row.get("DS1-Theta_0", None)
                theta1 = time_row.get("DS1-Theta_1", 0.40)
                if pd.notna(theta0) and theta0 != "":
                    rv_reg.add_RV(
                        uq.rv_class_map("lognormal")(
                            name="replacement-Time",
                            theta=[float(theta0), float(theta1) if pd.notna(theta1) else 0.40],
                        )
                    )

            thresholds = {"Cost": 1.0}  # trigger replacement at 100% cost
            return (rv_reg, thresholds)

        except Exception as exc:
            log.debug("Could not build replacement config: %s", exc)
            return None

    def _get_replacement_cost(self) -> float:
        """Return the replacement cost (PHP_2020) for loss ratio computation."""
        # Check metadata for archetype-specific value
        arch_cost = self.metadata.get("replacement_cost_PHP")
        if arch_cost:
            return float(arch_cost)

        # Fall back to replacement.csv placeholder
        try:
            repl_path = _get_data_path("replacement.csv")
            repl_df = pd.read_csv(repl_path, index_col=0)
            if "replacement-Cost" in repl_df.index:
                theta0 = repl_df.loc["replacement-Cost", "DS1-Theta_0"]
                if pd.notna(theta0) and str(theta0) != "":
                    return float(theta0)
        except Exception:
            pass

        # Default: 0 → loss_ratio will be 0 (avoid division by zero)
        return 0.0
