"""Python bridge to the C++ path engine.

Provides a unified interface that uses the C++ ``skymind_cpp`` module when
available and falls back to the pure-Python implementations otherwise.
"""

from __future__ import annotations

import time
from typing import Any

from models.common import Position3D

# Try to import the C++ module
_CPP_AVAILABLE = False
try:
    import skymind_cpp as _cpp  # type: ignore[import-untyped]
    _CPP_AVAILABLE = True
except ImportError:
    _cpp = None


def cpp_available() -> bool:
    """Return True if the C++ engine is importable."""
    return _CPP_AVAILABLE


def _to_cpp_pos(p: Position3D) -> Any:
    """Convert a Python Position3D to a C++ Position3D."""
    return _cpp.Position3D(p.lat, p.lon, p.alt_m)  # type: ignore[union-attr]


def _from_cpp_pos(cp: Any) -> Position3D:
    """Convert a C++ Position3D to a Python Position3D."""
    return Position3D(lat=cp.lat, lon=cp.lon, alt_m=cp.alt_m)


def _to_cpp_zones(zones: list[dict]) -> list[Any]:
    rz_list = []
    for z in zones:
        rz = _cpp.RestrictedZone()  # type: ignore[union-attr]
        rz.center_lat = z["center_lat"]
        rz.center_lon = z["center_lon"]
        rz.radius_m = z["radius_m"]
        rz.floor_m = z.get("floor_m", 0)
        rz.ceiling_m = z.get("ceiling_m", 999999)
        rz_list.append(rz)
    return rz_list


class CppPathEngine:
    """Unified path engine with C++ acceleration and Python fallback.

    Parameters
    ----------
    use_cpp :
        If True, use C++ when available.  If False, always use Python.
    """

    def __init__(self, use_cpp: bool = True) -> None:
        self._use_cpp = use_cpp and _CPP_AVAILABLE

    @property
    def using_cpp(self) -> bool:
        return self._use_cpp

    # ── A* ────────────────────────────────────────────────────────────

    def astar_find_path(
        self,
        start: Position3D,
        goal: Position3D,
        restricted_zones: list[dict] | None = None,
        grid_resolution_m: float = 100.0,
        altitude_step_m: float = 10.0,
        reference_lat: float = 37.5665,
        max_iterations: int = 50_000,
    ) -> list[Position3D]:
        if self._use_cpp:
            pf = _cpp.AStarPathfinder(  # type: ignore[union-attr]
                grid_resolution_m, altitude_step_m,
                30.0, 400.0, 2.0, reference_lat,
            )
            if restricted_zones:
                pf.set_restricted_zones(_to_cpp_zones(restricted_zones))
            result = pf.find_path(_to_cpp_pos(start), _to_cpp_pos(goal), max_iterations)
            return [_from_cpp_pos(p) for p in result]

        from core.path_engine.astar import AStarPathfinder
        pf_py = AStarPathfinder(
            grid_resolution_m=grid_resolution_m,
            altitude_step_m=altitude_step_m,
            reference_lat=reference_lat,
        )
        if restricted_zones:
            pf_py.set_restricted_zones(restricted_zones)
        return pf_py.find_path(start, goal, max_iterations=max_iterations)

    # ── RRT* ──────────────────────────────────────────────────────────

    def rrt_find_path(
        self,
        start: Position3D,
        goal: Position3D,
        restricted_zones: list[dict] | None = None,
        step_m: float = 200.0,
        search_radius_m: float = 500.0,
        reference_lat: float = 37.5665,
        max_iterations: int = 3000,
        seed: int | None = None,
    ) -> list[Position3D]:
        if self._use_cpp:
            pf = _cpp.RRTStarPathfinder(  # type: ignore[union-attr]
                step_m, search_radius_m, 30.0, 400.0, reference_lat, 150.0,
            )
            if restricted_zones:
                pf.set_restricted_zones(_to_cpp_zones(restricted_zones))
            result = pf.find_path(
                _to_cpp_pos(start), _to_cpp_pos(goal),
                max_iterations, seed if seed is not None else -1,
            )
            return [_from_cpp_pos(p) for p in result]

        from core.path_engine.rrt_star import RRTStarPathfinder
        pf_py = RRTStarPathfinder(
            step_m=step_m,
            search_radius_m=search_radius_m,
            reference_lat=reference_lat,
        )
        if restricted_zones:
            pf_py.set_restricted_zones(restricted_zones)
        return pf_py.find_path(start, goal, max_iterations=max_iterations, seed=seed)

    # ── optimizer ─────────────────────────────────────────────────────

    def smooth_path(
        self,
        path: list[Position3D],
        weight_smooth: float = 0.3,
        weight_data: float = 0.5,
    ) -> list[Position3D]:
        if self._use_cpp:
            cpp_path = [_to_cpp_pos(p) for p in path]
            result = _cpp.smooth_path(cpp_path, weight_smooth, weight_data)  # type: ignore[union-attr]
            return [_from_cpp_pos(p) for p in result]

        from core.path_engine.optimizer import smooth_path
        return smooth_path(path, weight_smooth=weight_smooth, weight_data=weight_data)

    def simplify_path(
        self,
        path: list[Position3D],
        epsilon_m: float = 10.0,
    ) -> list[Position3D]:
        if self._use_cpp:
            cpp_path = [_to_cpp_pos(p) for p in path]
            result = _cpp.simplify_path(cpp_path, epsilon_m)  # type: ignore[union-attr]
            return [_from_cpp_pos(p) for p in result]

        from core.path_engine.optimizer import simplify_path
        return simplify_path(path, epsilon_m=epsilon_m)

    # ── benchmark ─────────────────────────────────────────────────────

    def benchmark(
        self,
        func_name: str,
        n_runs: int = 100,
        **kwargs: Any,
    ) -> dict:
        """Run a benchmark comparing C++ vs Python for the named function.

        Returns dict with cpp_mean_ms, py_mean_ms, speedup.
        """
        func_map = {
            "astar": self.astar_find_path,
            "rrt": self.rrt_find_path,
            "smooth": self.smooth_path,
            "simplify": self.simplify_path,
        }
        if func_name not in func_map:
            raise ValueError(f"Unknown function: {func_name}")

        results: dict[str, float] = {}

        # Python timing
        orig = self._use_cpp
        self._use_cpp = False
        py_times = []
        for _ in range(n_runs):
            t0 = time.perf_counter()
            try:
                func_map[func_name](**kwargs)
            except Exception:
                pass
            py_times.append((time.perf_counter() - t0) * 1000)
        results["py_mean_ms"] = sum(py_times) / len(py_times) if py_times else 0

        # C++ timing
        if _CPP_AVAILABLE:
            self._use_cpp = True
            cpp_times = []
            for _ in range(n_runs):
                t0 = time.perf_counter()
                try:
                    func_map[func_name](**kwargs)
                except Exception:
                    pass
                cpp_times.append((time.perf_counter() - t0) * 1000)
            results["cpp_mean_ms"] = sum(cpp_times) / len(cpp_times) if cpp_times else 0
        else:
            results["cpp_mean_ms"] = float("nan")

        self._use_cpp = orig

        py_ms = results["py_mean_ms"]
        cpp_ms = results["cpp_mean_ms"]
        if cpp_ms > 0 and py_ms > 0:
            results["speedup"] = py_ms / cpp_ms
        else:
            results["speedup"] = float("nan")

        return results
