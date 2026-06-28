"""Shared pytest fixtures for the bayanihan test suite."""
import pytest
import numpy as np


@pytest.fixture
def dummy_edp_samples():
    """Small EDP sample array for unit tests.

    Shape: (n_simulations=50, n_stories=3, n_edp_types=2)
    EDP types: [PID (rad), PFA (g)]
    """
    rng = np.random.default_rng(42)
    pid = rng.lognormal(mean=-3.5, sigma=0.6, size=(50, 3))  # ~3% drift median
    pfa = rng.lognormal(mean=-1.2, sigma=0.5, size=(50, 3))  # ~0.3g median
    return np.stack([pid, pfa], axis=-1)


@pytest.fixture
def dummy_rupture():
    """WVF Mw=7.3 scenario from thesis Chapter 7."""
    return {
        "Mw": 7.3,
        "lat": 14.35,
        "lon": 121.10,
        "depth": 20.0,
        "mechanism": "interface",
    }
