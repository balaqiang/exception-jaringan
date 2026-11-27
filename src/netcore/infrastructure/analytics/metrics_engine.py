"""NumPy-vectorised telemetry math (DEC-017)."""

from __future__ import annotations

import math

import numpy as np

from netcore.application.dto import LatencyMetricsDTO

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _finite(value: float, default: float = 0.0) -> float:
    return value if math.isfinite(value) else default


def to_sparkline(values: np.ndarray, width: int = 10) -> str:
    """Render a fixed-width Unicode sparkline from a numeric array."""
    if values.size == 0:
        return SPARK_CHARS[0] * width
    tail = values[-width:]
    clean = np.nan_to_num(tail, nan=0.0, posinf=100.0, neginf=0.0)
    low, high = float(clean.min()), float(clean.max())
    if high - low < 1e-9:
        index = np.zeros(clean.size, dtype=np.int64)
    else:
        scaled = (clean - low) / (high - low) * (len(SPARK_CHARS) - 1)
        index = np.clip(np.rint(scaled).astype(np.int64), 0, len(SPARK_CHARS) - 1)
    bars = "".join(SPARK_CHARS[int(item)] for item in index)
    return bars.rjust(width, SPARK_CHARS[0])


class MetricsEngine:
    """Latency percentiles, per-link EMA ring buffers and anomaly flags."""

    def __init__(self, buffer_size: int = 24, alpha: float = 0.3) -> None:
        self._buffer_size = buffer_size
        self._alpha = alpha
        self._buffers: dict[int, np.ndarray] = {}
        self._ema: dict[int, float] = {}

    def reset(self) -> None:
        """Drop all ring buffers."""
        self._buffers.clear()
        self._ema.clear()

    def latency_metrics(self, values: np.ndarray | list[float]) -> LatencyMetricsDTO:
        """Compute mean/p50/p95/p99/max safely."""
        array = np.asarray(values, dtype=np.float64)
        array = array[np.isfinite(array)]
        if array.size == 0:
            return LatencyMetricsDTO(
                sample_count=0,
                mean_ms=0.0,
                p50_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                max_ms=0.0,
                sparkline=SPARK_CHARS[0] * 10,
            )
        p50, p95, p99 = np.percentile(array, [50, 95, 99])
        return LatencyMetricsDTO(
            sample_count=int(array.size),
            mean_ms=round(_finite(float(np.mean(array))), 3),
            p50_ms=round(_finite(float(p50)), 3),
            p95_ms=round(_finite(float(p95)), 3),
            p99_ms=round(_finite(float(p99)), 3),
            max_ms=round(_finite(float(np.max(array))), 3),
            sparkline=to_sparkline(array[-24:], width=10),
        )

    def update_link(
        self, link_id: int, utilization_pct: float
    ) -> tuple[float, str, bool]:
        """Push a sample into a link ring buffer; return EMA, sparkline, anomaly."""
        value = _finite(float(utilization_pct), 0.0)
        value = float(np.clip(value, 0.0, 100.0))
        buffer = self._buffers.get(link_id)
        if buffer is None:
            buffer = np.zeros(self._buffer_size, dtype=np.float64)
        buffer = np.roll(buffer, -1)
        buffer[-1] = value
        self._buffers[link_id] = buffer
        previous = self._ema.get(link_id, value)
        ema = self._alpha * value + (1 - self._alpha) * previous
        self._ema[link_id] = ema
        mean = float(np.mean(buffer))
        sigma = float(np.std(buffer))
        z_score = (value - mean) / max(sigma, 1e-6)
        anomaly = value > 90.0 or (sigma > 1.0 and z_score > 2.5)
        return round(_finite(ema), 2), to_sparkline(buffer, width=10), anomaly

    def column_quantiles(self, values: np.ndarray) -> dict[str, float]:
        """Return finite mean/p50/p95 for a numeric column."""
        array = np.asarray(values, dtype=np.float64)
        array = array[np.isfinite(array)]
        if array.size == 0:
            return {"mean": 0.0, "p50": 0.0, "p95": 0.0}
        p50, p95 = np.percentile(array, [50, 95])
        return {
            "mean": round(_finite(float(np.mean(array))), 2),
            "p50": round(_finite(float(p50)), 2),
            "p95": round(_finite(float(p95)), 2),
        }
