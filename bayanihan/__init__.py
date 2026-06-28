"""bayanihan — seismic resilience assessment for Philippine school building portfolios.

Open-source port of the methodology from Jeswani et al. (2022) and Jeswani (2021) onto
Pelicun. Built by AI agents (Claude Code) under the author's direction. Experimental —
see DISCLAIMER.md before use.

References:
    Jeswani et al. (2022). Seismic risk assessment and
    mitigation analysis of large public school building portfolios in Metro Manila.
    Earthquake Spectra, 38(3), 1946–1971.
    https://doi.org/10.1177/87552930221086304

    Jeswani, K. K. (2021). The Seismic Resilience of Critical Spatially-Distributed
    Building Portfolios. MASc thesis, University of Toronto.
    https://utoronto.scholaris.ca/items/4e628627-fb5b-4674-bac1-e20cb503a1f5
"""

__version__ = "0.0.0"
__author__ = "Kevin Jeswani"
__license__ = "Apache-2.0"

from bayanihan.archetypes import ARCHETYPE_IDS, get_archetype, list_archetypes
from bayanihan.building import Building
from bayanihan.hazard import (
    HazardModel,
    ThesisHazardModel,
    scenario_sa_field,
)
from bayanihan.portfolio import (
    MITIGATION_RETROFIT_MAP,
    PortfolioAnalysis,
    ScenarioPortfolio,
    ScenarioPortfolioResult,
    mitigation_coverage,
    summarise_scenario_result,
)

__all__ = [
    "Building",
    "PortfolioAnalysis",
    "ScenarioPortfolio",
    "ScenarioPortfolioResult",
    "summarise_scenario_result",
    "mitigation_coverage",
    "MITIGATION_RETROFIT_MAP",
    "HazardModel",
    "ThesisHazardModel",
    "scenario_sa_field",
    "get_archetype",
    "list_archetypes",
    "ARCHETYPE_IDS",
    "__version__",
]
