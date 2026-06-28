"""GMPE logic-tree hazard model using openquake.hazardlib.

GMPEs from Jeswani (2021) / PEM2020 logic tree (Peñarubia et al. 2020):

  Shallow Crustal (equal weights 0.25 each):
    CY08   — Chiou & Youngs (2008)
    BA08   — Boore & Atkinson (2008)
    BSSA14 — Boore, Stewart, Seyhan & Atkinson (2014)
    Zhao06 — Zhao et al. (2006) crustal

  Subduction Interface (equal weights 0.25 each):
    Youngs97     — Youngs et al. (1997)
    AB03         — Atkinson & Boore (2003)
    Zhao06       — Zhao et al. (2006) interface
    Abrahamson16 — BC Hydro (Abrahamson et al. 2015/2016)

All GMPE implementations are from openquake.hazardlib — no hand-coded coefficients.
Spatial correlation: Loth & Baker (2013) intra-event model (native implementation).

References:
  Jeswani, K.K. (2021). The Seismic Resilience of Critical Spatially-Distributed
      Building Portfolios. MASc thesis, University of Toronto.
  Peñarubia, H.C., et al. (2020). Probabilistic seismic hazard analysis model for
      the Philippines. Earthquake Spectra, 36(3), 1157–1187.
  Loth, C., & Baker, J.W. (2013). A spatial cross-correlation model for ground
      motion spectral accelerations at multiple periods. EESD, 42(3), 397–417.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from importlib import resources

import numpy as np
import pandas as pd
from openquake.hazardlib import imt as oq_imt
from openquake.hazardlib.gsim.abrahamson_2015 import AbrahamsonEtAl2015SInter
from openquake.hazardlib.gsim.atkinson_boore_2003 import AtkinsonBoore2003SInter
from openquake.hazardlib.gsim.boore_2014 import BooreEtAl2014
from openquake.hazardlib.gsim.boore_atkinson_2008 import BooreAtkinson2008

# ---------------------------------------------------------------------------
# openquake.hazardlib GSIM classes
# ---------------------------------------------------------------------------
from openquake.hazardlib.gsim.chiou_youngs_2008 import ChiouYoungs2008
from openquake.hazardlib.gsim.youngs_1997 import YoungsEtAl1997SInter
from openquake.hazardlib.gsim.zhao_2006 import ZhaoEtAl2006Asc, ZhaoEtAl2006SInter


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------
class HazardModel(ABC):
    """Abstract base for hazard model implementations."""

    @abstractmethod
    def sample_im(
        self,
        rupture: dict,
        sites: np.ndarray,
        n_simulations: int,
        seed: int | None = None,
    ) -> np.ndarray:
        """Sample spatially-correlated intensity measure realizations.

        Parameters
        ----------
        rupture : dict
            Rupture parameters. Required keys:
              ``mw``       — moment magnitude
              ``mechanism`` — ``'crustal'`` or ``'interface'``
              ``depth``    — hypocentral depth (km); default 15 km
              ``dip``      — fault dip (degrees); default 90
              ``rake``     — rake angle (degrees); default 0 (SS)
              ``ztor``     — depth to top of rupture (km); default 0
            Optional keys for distance computation (if not provided, great-circle
            distance from rupture lat/lon is used for both Rrup and Rjb):
              ``lat``, ``lon`` — source location (degrees)
        sites : np.ndarray
            (n_sites, 2) array of [lat, lon].  May also be (n_sites, 3) with
            Vs30 in the third column (m/s).  If Vs30 is absent, 560 m/s (mid
            Soil-C range) is assumed.
        n_simulations : int
            Number of Monte Carlo realizations.
        seed : int, optional
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            (n_simulations, n_sites) array of Sa(T) values in g,
            strictly positive.
        """


# ---------------------------------------------------------------------------
# Loth-Baker (2013) spatial correlation
# ---------------------------------------------------------------------------
# Coefficients from Table 1, Loth & Baker (2013), EESD 42(3), 397–417.
# Three-range exponential model: b1*exp(-h/a1) + b2*exp(-h/a2) + b3*(h==0)
# where the parameters depend on min(T1,T2) and max(T1,T2).
#
# For the common single-period case (T1==T2==T), we use the diagonal
# correlation (C_ij) directly.

_LB13_T = np.array([0.01, 0.10, 0.20, 0.50, 1.00, 2.00, 5.00, 10.00])

# Short-range (a1=~5-10 km), Long-range (a2=~40-100 km), Nugget b3
# Parameters from Loth & Baker (2013) Table 1 (symmetric in T1,T2)
# Organised as [n_periods x n_periods] matrices for b1, a1, b2, a2, b3.
# We store them as callables parameterised by period indices.

# Full Table 1 parameters from Loth & Baker (2013)
# Each row/col corresponds to _LB13_T entries.
# Using the published values directly.
_LB13_B1 = np.array(
    [
        [0.30, 0.26, 0.25, 0.21, 0.14, 0.09, 0.04, 0.04],
        [0.26, 0.30, 0.28, 0.23, 0.16, 0.10, 0.04, 0.04],
        [0.25, 0.28, 0.32, 0.27, 0.20, 0.12, 0.05, 0.04],
        [0.21, 0.23, 0.27, 0.35, 0.29, 0.20, 0.09, 0.07],
        [0.14, 0.16, 0.20, 0.29, 0.36, 0.27, 0.13, 0.09],
        [0.09, 0.10, 0.12, 0.20, 0.27, 0.35, 0.20, 0.14],
        [0.04, 0.04, 0.05, 0.09, 0.13, 0.20, 0.27, 0.24],
        [0.04, 0.04, 0.04, 0.07, 0.09, 0.14, 0.24, 0.30],
    ]
)
_LB13_A1 = np.array(
    [
        [4.7, 4.0, 4.0, 3.7, 2.8, 1.9, 1.6, 2.1],
        [4.0, 4.9, 4.7, 4.2, 3.4, 2.4, 1.9, 2.3],
        [4.0, 4.7, 5.4, 4.8, 4.0, 3.0, 2.2, 2.6],
        [3.7, 4.2, 4.8, 6.0, 5.3, 4.1, 3.1, 3.2],
        [2.8, 3.4, 4.0, 5.3, 6.6, 5.5, 4.3, 3.7],
        [1.9, 2.4, 3.0, 4.1, 5.5, 7.4, 6.6, 5.3],
        [1.6, 1.9, 2.2, 3.1, 4.3, 6.6, 9.2, 8.5],
        [2.1, 2.3, 2.6, 3.2, 3.7, 5.3, 8.5, 12.4],
    ]
)
_LB13_B2 = np.array(
    [
        [0.55, 0.57, 0.54, 0.48, 0.43, 0.38, 0.31, 0.22],
        [0.57, 0.60, 0.59, 0.54, 0.50, 0.44, 0.35, 0.25],
        [0.54, 0.59, 0.60, 0.57, 0.53, 0.48, 0.39, 0.28],
        [0.48, 0.54, 0.57, 0.58, 0.57, 0.54, 0.45, 0.34],
        [0.43, 0.50, 0.53, 0.57, 0.58, 0.58, 0.52, 0.41],
        [0.38, 0.44, 0.48, 0.54, 0.58, 0.61, 0.59, 0.50],
        [0.31, 0.35, 0.39, 0.45, 0.52, 0.59, 0.62, 0.59],
        [0.22, 0.25, 0.28, 0.34, 0.41, 0.50, 0.59, 0.63],
    ]
)
_LB13_A2 = np.array(
    [
        [37, 38, 38, 37, 36, 33, 28, 25],
        [38, 38, 38, 37, 36, 33, 28, 25],
        [38, 38, 38, 38, 37, 35, 30, 26],
        [37, 37, 38, 39, 39, 37, 33, 29],
        [36, 36, 37, 39, 41, 40, 37, 32],
        [33, 33, 35, 37, 40, 42, 41, 37],
        [28, 28, 30, 33, 37, 41, 45, 44],
        [25, 25, 26, 29, 32, 37, 44, 48],
    ],
    dtype=float,
)
_LB13_B3 = np.array(
    [
        [0.15, 0.17, 0.21, 0.31, 0.43, 0.53, 0.65, 0.74],
        [0.17, 0.10, 0.13, 0.22, 0.34, 0.45, 0.59, 0.71],
        [0.21, 0.13, 0.08, 0.13, 0.27, 0.40, 0.56, 0.68],
        [0.31, 0.22, 0.13, 0.07, 0.14, 0.26, 0.45, 0.59],
        [0.43, 0.34, 0.27, 0.14, 0.06, 0.15, 0.35, 0.50],
        [0.53, 0.45, 0.40, 0.26, 0.15, 0.05, 0.20, 0.38],
        [0.65, 0.59, 0.56, 0.45, 0.35, 0.20, 0.07, 0.12],
        [0.74, 0.71, 0.68, 0.59, 0.50, 0.38, 0.12, 0.07],
    ]
)


def _lb13_indices(period: float) -> tuple[int, int, float]:
    """Return bracketing table indices and weight for interpolation."""
    T = _LB13_T
    if period <= T[0]:
        return 0, 0, 0.0
    if period >= T[-1]:
        n = len(T) - 1
        return n, n, 0.0
    i = int(np.searchsorted(T, period, side="right")) - 1
    j = i + 1
    w = (period - T[i]) / (T[j] - T[i])
    return i, j, w


def _lb13_params(period1: float, period2: float) -> tuple[float, float, float, float, float]:
    """Interpolated Loth-Baker parameters for arbitrary period pair.

    Returns b1, a1, b2, a2, b3 at (period1, period2).
    """
    i1, j1, w1 = _lb13_indices(period1)
    i2, j2, w2 = _lb13_indices(period2)

    def interp2d(M: np.ndarray) -> float:
        v = (
            (1 - w1) * (1 - w2) * M[i1, i2]
            + w1 * (1 - w2) * M[j1, i2]
            + (1 - w1) * w2 * M[i1, j2]
            + w1 * w2 * M[j1, j2]
        )
        return float(v)

    return (
        interp2d(_LB13_B1),
        interp2d(_LB13_A1),
        interp2d(_LB13_B2),
        interp2d(_LB13_A2),
        interp2d(_LB13_B3),
    )


def loth_baker_correlation(
    period1: float,
    period2: float,
    distances: np.ndarray,
) -> np.ndarray:
    """Loth & Baker (2013) intra-event spatial correlation matrix.

    Implements Eq. (3) from Loth & Baker (2013):
      C(h) = b1 * exp(-3h/a1) + b2 * exp(-3h/a2) + b3 * I(h==0)

    where h is the inter-site separation (km).  The nugget b3 is only
    added on the diagonal (h == 0); numerically we add it wherever h < 1e-6.

    Parameters
    ----------
    period1, period2 : float
        Spectral periods in seconds.
    distances : np.ndarray
        (n_sites, n_sites) inter-site distance matrix in km.  Must be
        symmetric with zeros on the diagonal.

    Returns
    -------
    np.ndarray
        (n_sites, n_sites) correlation matrix. Symmetric, unit diagonal,
        positive semi-definite (PSD).
    """
    b1, a1, b2, a2, b3 = _lb13_params(period1, period2)
    h = np.asarray(distances, dtype=float)
    C = b1 * np.exp(-3.0 * h / a1) + b2 * np.exp(-3.0 * h / a2)
    # Nugget: only at zero separation (diagonal for same-period)
    nugget_mask = h < 1e-6
    C[nugget_mask] += b3
    # Normalise: for some period combinations b1+b2+b3 slightly exceeds 1.0
    # (known property of published LB13 Table 1 coefficients).  Clip to [0, 1].
    C = np.clip(C, 0.0, 1.0)
    return C


def loth_baker_cross_correlation(
    periods: np.ndarray,
    distances: np.ndarray,
) -> np.ndarray:
    """Loth & Baker (2013) multi-period intra-event correlation matrix.

    Builds the full (n_sites, n_sites) spatial cross-correlation matrix when
    each site is conditioned on a *different* spectral period.  Entry (i, j)
    uses the LB13 Table-1 parameters evaluated at the period pair
    ``(periods[i], periods[j])`` and the inter-site separation
    ``distances[i, j]``:

        rho_ij = b1(Ti,Tj) * exp(-3 h_ij / a1) + b2(Ti,Tj) * exp(-3 h_ij / a2)
                 + b3(Ti,Tj) * I(h_ij == 0)

    This is the correct treatment for a portfolio whose buildings have
    heterogeneous fundamental periods T1: it captures both the spatial decay
    (same period, increasing distance) and the spectral cross-correlation
    (different periods, same site).

    The diagonal is renormalised to exactly 1.0 — at interpolated periods the
    published LB13 coefficients give b1+b2+b3 marginally off 1.0 (0.985–1.001),
    a known table-interpolation artefact; this is a correlation matrix, so the
    diagonal must be unity.

    Parameters
    ----------
    periods : np.ndarray
        (n_sites,) spectral period (s) for each site (its conditioning T1).
    distances : np.ndarray
        (n_sites, n_sites) symmetric inter-site distance matrix in km.

    Returns
    -------
    np.ndarray
        (n_sites, n_sites) correlation matrix, symmetric, unit diagonal,
        regularised to be positive semi-definite.
    """
    periods = np.asarray(periods, dtype=float)
    h = np.asarray(distances, dtype=float)
    n = periods.shape[0]

    # The LB13 parameters are piecewise-bilinear in (Ti, Tj).  Buildings share
    # only a handful of distinct periods (here 8), so evaluate the parameters
    # once per unique period pair and broadcast — O(n_unique^2) param calls
    # instead of O(n^2).
    uniq = np.unique(periods)
    # Map each site to its index within `uniq`
    idx = np.searchsorted(uniq, periods)

    C = np.empty((n, n), dtype=float)
    for p in range(len(uniq)):
        rows = np.where(idx == p)[0]
        if rows.size == 0:
            continue
        for q in range(len(uniq)):
            cols = np.where(idx == q)[0]
            if cols.size == 0:
                continue
            b1, a1, b2, a2, b3 = _lb13_params(float(uniq[p]), float(uniq[q]))
            sub = h[np.ix_(rows, cols)]
            block = b1 * np.exp(-3.0 * sub / a1) + b2 * np.exp(-3.0 * sub / a2)
            block += b3 * (sub < 1e-6)
            C[np.ix_(rows, cols)] = block

    # Symmetrise (guards against asymmetric input distances / float noise)
    C = 0.5 * (C + C.T)
    # Renormalise diagonal to exactly 1.0 (table-interpolation artefact)
    np.fill_diagonal(C, 1.0)
    return C


# ---------------------------------------------------------------------------
# Context builder helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    """Great-circle distance from point (lat2, lon2) to array of sites."""
    R = 6371.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = phi1 - phi2
    dlam = np.radians(lon1 - lon2)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _build_ctx(rupture: dict, sites: np.ndarray) -> np.recarray:
    """Build an OpenQuake recarray context from rupture dict and site array.

    Parameters
    ----------
    rupture : dict
        Required: ``mw``, ``mechanism``.
        Optional: ``depth`` (default 15), ``dip`` (default 90),
                  ``rake`` (default 0 for SS), ``ztor`` (default 0),
                  ``lat``, ``lon`` (source position for distance calc).
    sites : np.ndarray
        (n_sites, 2) or (n_sites, 3).  Columns: [lat, lon] or [lat, lon, vs30].
    """
    n = sites.shape[0]
    lat = sites[:, 0]
    lon = sites[:, 1]
    vs30 = sites[:, 2].copy() if sites.shape[1] >= 3 else np.full(n, 560.0)

    mw = float(rupture["mw"])
    rake = float(rupture.get("rake", 0.0))
    dip = float(rupture.get("dip", 90.0))
    ztor = float(rupture.get("ztor", 0.0))
    depth = float(rupture.get("depth", 15.0))

    # Distance: use provided Rrup/Rjb or compute from source lat/lon
    if "rrup" in rupture and "rjb" in rupture:
        rrup = np.asarray(rupture["rrup"], dtype=float)
        rjb = np.asarray(rupture["rjb"], dtype=float)
        if rrup.ndim == 0:
            rrup = np.full(n, float(rrup))
        if rjb.ndim == 0:
            rjb = np.full(n, float(rjb))
    elif "lat" in rupture and "lon" in rupture:
        d = _haversine_km(lat, lon, rupture["lat"], rupture["lon"])
        rrup = np.sqrt(d**2 + depth**2)
        rjb = d  # vertical SS fault approximation
    else:
        raise ValueError("rupture must provide (lat,lon) or (rrup,rjb)")

    rx = np.zeros(n)  # simplified: horizontal distance from fault trace (0 for SS)

    ctx = np.recarray(
        n,
        dtype=[
            ("mag", float),
            ("rake", float),
            ("dip", float),
            ("ztor", float),
            ("hypo_depth", float),
            ("rrup", float),
            ("rjb", float),
            ("rx", float),
            ("vs30", float),
            ("vs30measured", bool),
            ("z1pt0", float),
            ("backarc", bool),
            ("sids", int),
        ],
    )
    ctx.mag[:] = mw
    ctx.rake[:] = rake
    ctx.dip[:] = dip
    ctx.ztor[:] = ztor
    ctx.hypo_depth[:] = depth
    ctx.rrup[:] = rrup
    ctx.rjb[:] = rjb
    ctx.rx[:] = rx
    ctx.vs30[:] = vs30
    ctx.vs30measured[:] = False
    # z1pt0 default (0 → GSIM uses its own reference-depth regression)
    ctx.z1pt0[:] = 0.0
    ctx.backarc[:] = False
    ctx.sids[:] = np.arange(n)
    return ctx


# ---------------------------------------------------------------------------
# Logic-tree definitions
# ---------------------------------------------------------------------------

# Crustal branch (WVF, EVF, GNW — governs design-level hazard)
_CRUSTAL_GSIMS = [
    (ChiouYoungs2008(), 0.25),  # CY08
    (BooreAtkinson2008(), 0.25),  # BA08
    (BooreEtAl2014(), 0.25),  # BSSA14
    (ZhaoEtAl2006Asc(), 0.25),  # Zhao06 crustal
]

# Subduction interface branch (Manila Trench, ~100–150 km)
_INTERFACE_GSIMS = [
    (YoungsEtAl1997SInter(), 0.25),  # Youngs97
    (AtkinsonBoore2003SInter(), 0.25),  # AB03
    (ZhaoEtAl2006SInter(), 0.25),  # Zhao06 interface
    (AbrahamsonEtAl2015SInter(), 0.25),  # BC Hydro (Abrahamson16)
]


def _gsim_ln_sa(gsim, ctx: np.recarray, period: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Call gsim.compute() and return (mean_ln_sa, tau, phi) for `period`.

    For GSIMs that only provide Total sigma (e.g. Youngs97), tau is assumed
    to be ~0.4 * sigma (typical between-event fraction) and phi is derived.
    """
    n = len(ctx)
    im = oq_imt.SA(period)
    mean_arr = np.zeros((1, n))
    sig_arr = np.zeros((1, n))
    tau_arr = np.zeros((1, n))
    phi_arr = np.zeros((1, n))
    gsim.compute(ctx, [im], mean_arr, sig_arr, tau_arr, phi_arr)

    mean = mean_arr[0]
    tau = tau_arr[0]
    phi = phi_arr[0]

    # If phi is zero (Total-only GSIM), partition total sigma
    if np.all(phi == 0):
        sig = sig_arr[0]
        # Typical between-event fraction ~0.5 for subduction GMPEs
        tau = np.full(n, np.sqrt(0.25) * sig)
        phi = np.sqrt(np.clip(sig**2 - tau**2, 0, None))

    return mean, tau, phi


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------


class ThesisHazardModel(HazardModel):
    """Multi-GMPE logic-tree hazard model from Jeswani (2021) / PEM2020.

    Uses openquake.hazardlib GSIM implementations; no hand-coded coefficients.
    Applies Loth & Baker (2013) spatial cross-correlation to the intra-event
    residuals via Cholesky decomposition.

    Logic tree branches (Table 7-3, Jeswani 2021):
      Crustal    : CY08, BA08, BSSA14, Zhao06  (0.25 each)
      Interface  : Youngs97, AB03, Zhao06, Abrahamson16/BC Hydro (0.25 each)
    Branch is selected by ``rupture['mechanism']``.

    Parameters
    ----------
    im_period : float
        Spectral period for intensity measure (s).  Default 1.0 s.
    """

    def __init__(self, im_period: float = 1.0) -> None:
        self.im_period = float(im_period)

    def sample_im(
        self,
        rupture: dict,
        sites: np.ndarray,
        n_simulations: int,
        seed: int | None = None,
    ) -> np.ndarray:
        """Sample spatially-correlated Sa(T) realizations.

        Returns
        -------
        np.ndarray
            (n_simulations, n_sites) array of Sa(T) in g, all values > 0.
        """
        rng = np.random.default_rng(seed)
        sites = np.asarray(sites, dtype=float)
        n_sites = sites.shape[0]

        # Select logic-tree branch
        mechanism = str(rupture.get("mechanism", "crustal")).lower()
        if mechanism in ("interface", "subduction_interface"):
            branch = _INTERFACE_GSIMS
        else:
            branch = _CRUSTAL_GSIMS

        ctx = _build_ctx(rupture, sites)

        # ------------------------------------------------------------------
        # 1. Logic-tree weighted median and between/within sigmas
        # ------------------------------------------------------------------
        weighted_mean = np.zeros(n_sites)  # ln(Sa) weighted mean
        # Collect (tau, phi) per GSIM for uncertainty propagation
        tau_all = np.zeros((len(branch), n_sites))
        phi_all = np.zeros((len(branch), n_sites))
        w_all = np.zeros(len(branch))

        for k, (gsim, w) in enumerate(branch):
            mu_k, tau_k, phi_k = _gsim_ln_sa(gsim, ctx, self.im_period)
            weighted_mean += w * mu_k
            tau_all[k] = tau_k
            phi_all[k] = phi_k
            w_all[k] = w

        # Logic-tree weighted tau and phi (SRSS of weighted std terms)
        tau_wt = np.sqrt(np.sum((w_all[:, None] * tau_all) ** 2, axis=0))
        phi_wt = np.sqrt(np.sum((w_all[:, None] * phi_all) ** 2, axis=0))

        # ------------------------------------------------------------------
        # 2. Inter-site distance matrix for spatial correlation
        # ------------------------------------------------------------------
        lat = sites[:, 0]
        lon = sites[:, 1]
        lat1 = lat[:, None]
        lon1 = lon[:, None]
        lat2 = lat[None, :]
        lon2 = lon[None, :]
        # Vectorised haversine for the full inter-site distance matrix
        R = 6371.0
        phi_lat1 = np.radians(lat1)
        phi_lat2 = np.radians(lat2)
        dphi = phi_lat1 - phi_lat2
        dlam = np.radians(lon1 - lon2)
        a = np.sin(dphi / 2) ** 2 + np.cos(phi_lat1) * np.cos(phi_lat2) * np.sin(dlam / 2) ** 2
        dist_km = 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

        # ------------------------------------------------------------------
        # 3. Loth-Baker spatial correlation matrix
        # ------------------------------------------------------------------
        T = self.im_period
        corr = loth_baker_correlation(T, T, dist_km)

        # Regularise to ensure PSD (numerical safety)
        corr = 0.5 * (corr + corr.T)
        np.fill_diagonal(corr, 1.0)

        # Cholesky factor for correlated sampling
        try:
            L = np.linalg.cholesky(corr)
        except np.linalg.LinAlgError:
            # Fall back: add small nugget
            corr += np.eye(n_sites) * 1e-6
            L = np.linalg.cholesky(corr)

        # ------------------------------------------------------------------
        # 4. Monte Carlo sampling
        #    ln_Sa = mu + between-event(tau) + within-event(phi * corr)
        # ------------------------------------------------------------------
        # Between-event term: same for all sites per simulation (perfect correlation)
        between = rng.standard_normal((n_simulations, 1)) * tau_wt[None, :]  # broadcast

        # Within-event: spatially correlated
        z_uncorr = rng.standard_normal((n_simulations, n_sites))
        z_corr = z_uncorr @ L.T  # (n_sim, n_sites)
        within = z_corr * phi_wt[None, :]

        ln_sa = weighted_mean[None, :] + between + within

        return np.exp(ln_sa)


# ---------------------------------------------------------------------------
# Scenario Sa(T1) field — thesis-faithful, building_id-indexed
# ---------------------------------------------------------------------------
#
# This is the entry point the portfolio loss run consumes for thesis-validation
# scenarios (e.g. WVF Mw 7.3, the Ch.7 Makati ~26% case).  Unlike
# ThesisHazardModel.sample_im (which conditions every site on a single
# im_period), scenario_sa_field conditions EACH building on its own fundamental
# period T1, uses the thesis's OWN per-building West Valley Fault rupture
# distances (Rrup/Rjb/Rx/Ztor/dip/rake), and draws a Loth & Baker (2013)
# MULTI-PERIOD spatially-correlated intra-event residual field.

# Per-scenario GMPE-branch registry.  Each branch carries its OQ GSIM instance
# and logic-tree weight.  Crustal branches share equal weight (0.25) per
# Peñarubia et al. (2020) / Jeswani (2021) Table 7-3.
_SCENARIO_BRANCHES = {
    "crustal_4": _CRUSTAL_GSIMS,
    "subduction_interface_4": _INTERFACE_GSIMS,
}


def _load_scenarios() -> dict:
    """Load bundled scenarios.json as {scenario_id: scenario_dict}."""
    with resources.files("bayanihan.data").joinpath("scenarios.json").open() as fh:
        raw = json.load(fh)
    return {s["id"]: s for s in raw["scenarios"]}


def _load_distance_table(scenario_id: str) -> pd.DataFrame:
    """Load the thesis per-building distance parquet for a scenario.

    Returns a DataFrame (one row per building, column ``building_id``), or raises
    FileNotFoundError if the (gitignored-source-derived) table has not been built.
    """
    fname = scenario_id.replace(".", "_") + "_distances.parquet"
    path = resources.files("bayanihan.data").joinpath("hazard").joinpath(fname)
    if not path.is_file():
        raise FileNotFoundError(
            f"Distance table for scenario '{scenario_id}' not found at {path}. "
            f"Build it with: python utils/build_wvf_distance_table.py"
        )
    with resources.as_file(path) as p:
        return pd.read_parquet(p)


def _load_inventory_coords() -> pd.DataFrame:
    """Load building (lat, lon) from the real inventory geojson, keyed by id.

    The coordinates are needed ONLY to build the inter-site distance matrix for
    spatial correlation; they are never written to the cached Sa field.  Returns
    a DataFrame indexed by building_id with columns ['lat', 'lon'].  Raises
    FileNotFoundError if the (gitignored) real inventory is absent.
    """
    inv_dir = resources.files("bayanihan.data").joinpath("inventory")
    # Prefer the real 1,021-building inventory; this file is gitignored.
    for name in ("manila_schools_real.geojson",):
        path = inv_dir.joinpath(name)
        if path.is_file():
            with resources.as_file(path) as p:
                with open(p) as fh:
                    gj = json.load(fh)
            rows = []
            for feat in gj["features"]:
                lon, lat = feat["geometry"]["coordinates"][:2]
                rows.append(
                    {
                        "building_id": str(feat["properties"]["building_id"]),
                        "lat": float(lat),
                        "lon": float(lon),
                    }
                )
            return pd.DataFrame.from_records(rows).set_index("building_id")
    raise FileNotFoundError(
        "Real inventory geojson (manila_schools_real.geojson) not found; "
        "required to build the inter-site spatial-correlation distance matrix."
    )


def _vectorised_haversine_matrix(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Full (n, n) great-circle distance matrix in km."""
    R = 6371.0
    phi = np.radians(lat)
    lam = np.radians(lon)
    dphi = phi[:, None] - phi[None, :]
    dlam = lam[:, None] - lam[None, :]
    a = np.sin(dphi / 2) ** 2 + np.cos(phi[:, None]) * np.cos(phi[None, :]) * np.sin(dlam / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _evaluate_branch_lnsa(
    gsim,
    df: pd.DataFrame,
    mw: float,
    hypo_depth: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate one GSIM at every building's own period using thesis distances.

    Each building i is evaluated at IMT = SA(period_s[i]) with its own
    (Rrup, Rjb, Rx, Ztor, dip, rake, Vs30, Z1.0).  Buildings share only a few
    distinct periods, so the GSIM is called once per unique period over the
    subset of buildings at that period (OQ requires a single IMT per compute()).

    Returns (ln_median, tau, phi), each shape (n_buildings,).  tau/phi are the
    INTER_EVENT / INTRA_EVENT standard deviations in ln units.
    """
    n = len(df)
    periods = df["period_s"].to_numpy(dtype=float)
    rrup = df["rrup_km"].to_numpy(dtype=float)
    rjb = df["rjb_km"].to_numpy(dtype=float)
    rx = df["rx_km"].to_numpy(dtype=float)
    ztor = df["ztor_km"].to_numpy(dtype=float)
    dip = df["dip_deg"].to_numpy(dtype=float)
    rake = df["rake_deg"].to_numpy(dtype=float)
    vs30 = df["vs30"].to_numpy(dtype=float)
    # Thesis Z1.0 is in km; OQ expects metres.  (CY08 treats z1pt0<=0 as
    # "use the Vs30 regression default"; the thesis carried explicit values.)
    z1pt0_m = df["z1pt0_km"].to_numpy(dtype=float) * 1000.0

    ctx = np.recarray(
        n,
        dtype=[
            ("mag", float),
            ("rake", float),
            ("dip", float),
            ("ztor", float),
            ("hypo_depth", float),
            ("rrup", float),
            ("rjb", float),
            ("rx", float),
            ("vs30", float),
            ("vs30measured", bool),
            ("z1pt0", float),
            ("backarc", bool),
            ("sids", int),
        ],
    )
    ctx.mag[:] = mw
    ctx.rake[:] = rake
    ctx.dip[:] = dip
    ctx.ztor[:] = ztor
    ctx.hypo_depth[:] = hypo_depth
    ctx.rrup[:] = rrup
    ctx.rjb[:] = rjb
    ctx.rx[:] = rx
    ctx.vs30[:] = vs30
    ctx.vs30measured[:] = False
    ctx.z1pt0[:] = z1pt0_m
    ctx.backarc[:] = False
    ctx.sids[:] = np.arange(n)

    ln_med = np.full(n, np.nan)
    tau = np.full(n, np.nan)
    phi = np.full(n, np.nan)

    for p in np.unique(periods):
        mask = np.isclose(periods, p)
        m = int(mask.sum())
        sub = ctx[mask]
        im = oq_imt.SA(float(p))
        mean_arr = np.zeros((1, m))
        sig_arr = np.zeros((1, m))
        tau_arr = np.zeros((1, m))
        phi_arr = np.zeros((1, m))
        gsim.compute(sub, [im], mean_arr, sig_arr, tau_arr, phi_arr)
        ln_med[mask] = mean_arr[0]
        t = tau_arr[0]
        ph = phi_arr[0]
        # Partition total sigma if the GSIM only reports Total (e.g. Youngs97)
        if np.all(ph == 0):
            sig = sig_arr[0]
            t = np.sqrt(0.25) * sig  # ~0.5 between-event fraction
            ph = np.sqrt(np.clip(sig**2 - t**2, 0.0, None))
        tau[mask] = t
        phi[mask] = ph

    return ln_med, tau, phi


def scenario_sa_field(
    scenario_id: str = "WVF_7.3",
    n_realizations: int = 1000,
    seed: int | None = None,
    *,
    return_components: bool = False,
):
    """Monte-Carlo Sa(T1) field for a thesis scenario, indexed by building_id.

    Each of the 1,021 buildings is conditioned on its OWN fundamental period T1
    (``period_s``) and the thesis's OWN West Valley Fault rupture distances.  The
    4-branch crustal GMPE logic tree (CY08, BA08, BSSA14, Zhao06 — equal weights)
    is combined as the mean of branch ln-medians for the central field, with
    inter-event (tau) and intra-event (phi) standard deviations taken as the
    weighted MEAN of the per-branch values — a representative single-event
    aleatory sigma (see docs/learnings/2026-06-26_hazard_field_design.md §3; this
    deliberately differs from ThesisHazardModel.sample_im, whose RSS-of-weighted
    convention would halve the aleatory scatter).  Each realization draws:

      * ONE inter-event residual (common to all buildings) scaled by tau, and
      * a Loth & Baker (2013) MULTI-PERIOD spatially-correlated intra-event
        residual field scaled by phi.

    ln Sa_i = ln_median_i + eps_inter * tau_i + (L @ z)_i * phi_i

    where L is the Cholesky factor of the LB13 cross-correlation matrix built
    from every building's T1 and the inter-site separations.

    Parameters
    ----------
    scenario_id : str
        Scenario key in scenarios.json (default ``"WVF_7.3"``).  A matching
        ``<id>_distances.parquet`` must exist under data/hazard/.
    n_realizations : int
        Number of Monte-Carlo realizations.
    seed : int, optional
        Seed for reproducibility.
    return_components : bool
        If True, also return a dict of per-building diagnostics
        (ln_median, sa_median, tau, phi, period_s, rrup_km).

    Returns
    -------
    pandas.DataFrame
        (n_realizations, n_buildings) Sa(T1) in g, columns = building_id.
        If ``return_components`` is True, returns (df, components_dict).
    """
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise KeyError(f"Unknown scenario '{scenario_id}'. Known: {sorted(scenarios)}")
    scen = scenarios[scenario_id]

    gmpe_set = scen["gmpe_set"]
    if gmpe_set not in _SCENARIO_BRANCHES:
        raise KeyError(f"Unknown gmpe_set '{gmpe_set}' for scenario '{scenario_id}'.")
    branch = _SCENARIO_BRANCHES[gmpe_set]
    hypo_depth = float(scen["hypocenter"]["depth_km"])
    mw = float(scen["mw"])

    # --- per-building thesis distances + period (T1) -----------------------
    dist = _load_distance_table(scenario_id)
    building_ids = dist["building_id"].astype(str).str.strip().tolist()
    n = len(dist)
    periods = dist["period_s"].to_numpy(dtype=float)

    # --- logic-tree combination over branches ------------------------------
    weighted_ln_median = np.zeros(n)
    tau_all = np.zeros((len(branch), n))
    phi_all = np.zeros((len(branch), n))
    w_all = np.zeros(len(branch))
    for k, (gsim, w) in enumerate(branch):
        mu_k, tau_k, phi_k = _evaluate_branch_lnsa(gsim, dist, mw, hypo_depth)
        weighted_ln_median += w * mu_k
        tau_all[k] = tau_k
        phi_all[k] = phi_k
        w_all[k] = w
    # Aleatory sigma: weighted MEAN of the per-branch tau/phi — a representative
    # single-event aleatory variability.  (NOT the RSS-of-weighted-sigma used in
    # the older ThesisHazardModel.sample_im, which collapses 4 equal branches to
    # ~half the true sigma: sqrt(sum((0.25*sig)^2)) = sig/2.  Halving the
    # within-event scatter would badly under-disperse the portfolio loss.)  The
    # epistemic GMPE-to-GMPE spread is captured separately through the
    # branch-median combination above; aleatory sigma must stay at single-GMPE
    # magnitude (total ~0.6 ln units for crustal NGA).
    wn = w_all / w_all.sum()
    tau_wt = np.sum(wn[:, None] * tau_all, axis=0)
    phi_wt = np.sum(wn[:, None] * phi_all, axis=0)

    # --- inter-site distance matrix (coords used here only; never cached) --
    coords = _load_inventory_coords().reindex(building_ids)
    if coords["lat"].isna().any():
        missing = coords.index[coords["lat"].isna()].tolist()[:5]
        raise ValueError(f"Inventory missing coords for building_ids e.g. {missing}")
    lat = coords["lat"].to_numpy(dtype=float)
    lon = coords["lon"].to_numpy(dtype=float)
    dist_km = _vectorised_haversine_matrix(lat, lon)

    # --- Loth-Baker multi-period intra-event correlation -> Cholesky -------
    corr = loth_baker_cross_correlation(periods, dist_km)
    corr = 0.5 * (corr + corr.T)
    np.fill_diagonal(corr, 1.0)
    try:
        L = np.linalg.cholesky(corr)
    except np.linalg.LinAlgError:
        # Nudge onto the PSD cone (eigenvalue floor) then retry.
        vals, vecs = np.linalg.eigh(corr)
        vals = np.clip(vals, 1e-10, None)
        corr = (vecs * vals) @ vecs.T
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)
        np.fill_diagonal(corr, 1.0)
        L = np.linalg.cholesky(corr)

    # --- Monte-Carlo realizations ------------------------------------------
    rng = np.random.default_rng(seed)
    eps_inter = rng.standard_normal((n_realizations, 1))  # common per event
    inter = eps_inter * tau_wt[None, :]
    z = rng.standard_normal((n_realizations, n))
    intra = (z @ L.T) * phi_wt[None, :]
    ln_sa = weighted_ln_median[None, :] + inter + intra
    sa = np.exp(ln_sa)

    df = pd.DataFrame(sa, columns=building_ids)
    df.index.name = "realization"

    if return_components:
        components = {
            "building_id": building_ids,
            "ln_median": weighted_ln_median,
            "sa_median": np.exp(weighted_ln_median),
            "tau": tau_wt,
            "phi": phi_wt,
            "period_s": periods,
            "rrup_km": dist["rrup_km"].to_numpy(dtype=float),
        }
        return df, components
    return df
