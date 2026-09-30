"""Probability scores. probs is (n, k), outcomes is (n,) with the index of what happened."""

import numpy as np


def _onehot(outcomes: np.ndarray, k: int) -> np.ndarray:
    return np.eye(k)[np.asarray(outcomes, dtype=int)]


def log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs = np.asarray(probs, dtype=float)
    picked = probs[np.arange(len(probs)), np.asarray(outcomes, dtype=int)]
    return float(-np.mean(np.log(np.clip(picked, 1e-15, 1))))


def brier(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs = np.asarray(probs, dtype=float)
    return float(np.mean(np.sum((probs - _onehot(outcomes, probs.shape[1])) ** 2, axis=1)))


def rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Ranked Probability Score: for ordered outcomes (home < draw < away), so
    predicting a draw when the home side won is less wrong than predicting away."""
    probs = np.asarray(probs, dtype=float)
    k = probs.shape[1]
    diff = np.cumsum(probs, axis=1) - np.cumsum(_onehot(outcomes, k), axis=1)
    return float(np.mean(np.sum(diff[:, :-1] ** 2, axis=1) / (k - 1)))


def closing_line_value(taken_odds: np.ndarray, closing_odds: np.ndarray) -> float:
    """Average % by which the odds we took beat the closing odds. Consistently
    positive CLV is the best early evidence of a real edge."""
    return float(np.mean(np.asarray(taken_odds) / np.asarray(closing_odds) - 1))


def score(probs: np.ndarray, outcomes: np.ndarray) -> dict[str, float]:
    return {
        "log_loss": log_loss(probs, outcomes),
        "brier": brier(probs, outcomes),
        "rps": rps(probs, outcomes),
    }
