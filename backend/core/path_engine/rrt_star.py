"""RRT* (Rapidly-exploring Random Tree Star) 3D path planner.

Continuous-space pathfinding that avoids restricted zones and produces
smooth, near-optimal paths.  Intended as a Phase-3 upgrade over the
grid-based A* planner.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from models.common import Position3D

# ── coordinate helpers ──────────────────────────────────────────────

_DEG_TO_M_LAT = 111_320.0  # metres per degree of latitude


def _deg_to_m_lon(lat: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat))


def _pos_to_metres(p: Position3D, ref_lat: float) -> tuple[float, float, float]:
    """Convert WGS-84 to local metres relative to *ref_lat*."""
    mx = (p.lon - 0) * _deg_to_m_lon(ref_lat)
    my = p.lat * _DEG_TO_M_LAT
    return (mx, my, p.alt_m)


def _metres_to_pos(mx: float, my: float, mz: float, ref_lat: float) -> Position3D:
    lat = my / _DEG_TO_M_LAT
    lon = mx / _deg_to_m_lon(ref_lat)
    return Position3D(lat=lat, lon=lon, alt_m=mz)


def _dist3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


# ── restricted-zone collision check ────────────────────────────────

@dataclass
class _Sphere:
    cx: float
    cy: float
    floor: float
    ceiling: float
    radius: float


def _segment_collides(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    obstacles: list[_Sphere],
    samples: int = 10,
) -> bool:
    """Check whether the segment a→b passes through any obstacle."""
    for t in range(samples + 1):
        frac = t / samples
        px = a[0] + (b[0] - a[0]) * frac
        py = a[1] + (b[1] - a[1]) * frac
        pz = a[2] + (b[2] - a[2]) * frac
        for obs in obstacles:
            if obs.floor <= pz <= obs.ceiling:
                dx = px - obs.cx
                dy = py - obs.cy
                if math.sqrt(dx * dx + dy * dy) < obs.radius:
                    return True
    return False


# ── RRT* node ───────────────────────────────────────────────────────

@dataclass
class _Node:
    pos: tuple[float, float, float]
    parent: _Node | None = None
    cost: float = 0.0
    children: list[_Node] = field(default_factory=list)


# ── B-spline smoother ──────────────────────────────────────────────

def _bspline_smooth(
    points: list[tuple[float, float, float]],
    num_output: int = 0,
    degree: int = 3,
) -> list[tuple[float, float, float]]:
    """Uniform cubic B-spline approximation (De Boor simplified).

    Uses a simple averaging approach that preserves start/end points and
    produces a smoother curve through intermediate control points.
    """
    if len(points) <= 2:
        return list(points)

    if num_output <= 0:
        num_output = max(len(points) * 3, 20)

    # Duplicate start/end to clamp the spline
    n = len(points)
    ctrl = [points[0]] * degree + list(points) + [points[-1]] * degree
    m = len(ctrl)
    result: list[tuple[float, float, float]] = []

    for i in range(num_output):
        t = i / (num_output - 1) * (n - 1)
        seg = min(int(t), n - 2)
        u = t - seg
        idx = seg + degree  # offset by clamped prefix

        # Cubic basis (uniform)
        b0 = (1 - u) ** 3 / 6
        b1 = (3 * u ** 3 - 6 * u ** 2 + 4) / 6
        b2 = (-3 * u ** 3 + 3 * u ** 2 + 3 * u + 1) / 6
        b3 = u ** 3 / 6

        i0 = max(0, min(idx - 1, m - 1))
        i1 = max(0, min(idx, m - 1))
        i2 = max(0, min(idx + 1, m - 1))
        i3 = max(0, min(idx + 2, m - 1))

        px = b0 * ctrl[i0][0] + b1 * ctrl[i1][0] + b2 * ctrl[i2][0] + b3 * ctrl[i3][0]
        py = b0 * ctrl[i0][1] + b1 * ctrl[i1][1] + b2 * ctrl[i2][1] + b3 * ctrl[i3][1]
        pz = b0 * ctrl[i0][2] + b1 * ctrl[i1][2] + b2 * ctrl[i2][2] + b3 * ctrl[i3][2]
        result.append((px, py, pz))

    # Force-snap start and end
    result[0] = points[0]
    result[-1] = points[-1]
    return result


# ── main planner ────────────────────────────────────────────────────

class RRTStarPathfinder:
    """RRT* 3D path planner operating in continuous WGS-84 space.

    Parameters
    ----------
    step_m : float
        Maximum extension distance per iteration (metres).
    search_radius_m : float
        Neighbourhood radius for the *rewire* step.
    altitude_min_m / altitude_max_m : float
        Altitude bounds.
    reference_lat : float
        Latitude used for lon→metre conversion.
    """

    def __init__(
        self,
        step_m: float = 200.0,
        search_radius_m: float = 500.0,
        altitude_min_m: float = 30.0,
        altitude_max_m: float = 400.0,
        reference_lat: float = 37.5665,
        goal_threshold_m: float = 150.0,
    ) -> None:
        self.step_m = step_m
        self.search_radius_m = search_radius_m
        self.alt_min = altitude_min_m
        self.alt_max = altitude_max_m
        self.ref_lat = reference_lat
        self.goal_threshold_m = goal_threshold_m
        self._obstacles: list[_Sphere] = []

    # ── restricted zones ────────────────────────────────────────────

    def set_restricted_zones(self, zones: list[dict]) -> None:
        """Set cylindrical restricted zones.

        Each zone dict has keys ``center_lat``, ``center_lon``,
        ``radius_m``, ``floor_m``, ``ceiling_m`` – same format used by
        :class:`AStarPathfinder`.
        """
        self._obstacles = []
        for z in zones:
            cx = z["center_lon"] * _deg_to_m_lon(self.ref_lat)
            cy = z["center_lat"] * _DEG_TO_M_LAT
            self._obstacles.append(
                _Sphere(
                    cx=cx,
                    cy=cy,
                    floor=z.get("floor_m", 0),
                    ceiling=z.get("ceiling_m", 9999),
                    radius=z["radius_m"],
                )
            )

    # ── public API ──────────────────────────────────────────────────

    def find_path(
        self,
        start: Position3D,
        goal: Position3D,
        max_iterations: int = 3000,
        seed: int | None = None,
    ) -> list[Position3D]:
        """Find a near-optimal 3D path from *start* to *goal*.

        Returns a list of :class:`Position3D` waypoints.  Raises
        ``ValueError`` if no path is found within *max_iterations*.
        """
        if seed is not None:
            random.seed(seed)

        s_m = _pos_to_metres(start, self.ref_lat)
        g_m = _pos_to_metres(goal, self.ref_lat)

        root = _Node(pos=s_m)
        nodes: list[_Node] = [root]

        best_goal_node: _Node | None = None
        best_goal_cost = float("inf")

        # Sampling bounds (expanded around start/goal)
        margin = max(self.step_m * 5, _dist3(s_m, g_m) * 0.3)
        lo_x = min(s_m[0], g_m[0]) - margin
        hi_x = max(s_m[0], g_m[0]) + margin
        lo_y = min(s_m[1], g_m[1]) - margin
        hi_y = max(s_m[1], g_m[1]) + margin

        for _ in range(max_iterations):
            # Goal-biased sampling (20% chance)
            if random.random() < 0.2:
                rnd = g_m
            else:
                rx = random.uniform(lo_x, hi_x)
                ry = random.uniform(lo_y, hi_y)
                rz = random.uniform(self.alt_min, self.alt_max)
                rnd = (rx, ry, rz)

            # Nearest node
            nearest = min(nodes, key=lambda n: _dist3(n.pos, rnd))
            d = _dist3(nearest.pos, rnd)
            if d < 1e-9:
                continue

            # Steer towards random point
            if d > self.step_m:
                ratio = self.step_m / d
                new_pos = (
                    nearest.pos[0] + (rnd[0] - nearest.pos[0]) * ratio,
                    nearest.pos[1] + (rnd[1] - nearest.pos[1]) * ratio,
                    nearest.pos[2] + (rnd[2] - nearest.pos[2]) * ratio,
                )
            else:
                new_pos = rnd

            # Clamp altitude
            new_pos = (new_pos[0], new_pos[1], max(self.alt_min, min(self.alt_max, new_pos[2])))

            # Collision check
            if _segment_collides(nearest.pos, new_pos, self._obstacles):
                continue

            # RRT* rewire — find neighbours in radius
            new_cost = nearest.cost + _dist3(nearest.pos, new_pos)
            neighbours = [n for n in nodes if _dist3(n.pos, new_pos) < self.search_radius_m]

            # Choose best parent among neighbours
            best_parent = nearest
            best_cost = new_cost
            for nb in neighbours:
                c = nb.cost + _dist3(nb.pos, new_pos)
                if c < best_cost and not _segment_collides(nb.pos, new_pos, self._obstacles):
                    best_parent = nb
                    best_cost = c

            new_node = _Node(pos=new_pos, parent=best_parent, cost=best_cost)
            best_parent.children.append(new_node)
            nodes.append(new_node)

            # Rewire existing neighbours through new_node
            for nb in neighbours:
                if nb is best_parent:
                    continue
                c_via_new = best_cost + _dist3(new_pos, nb.pos)
                if c_via_new < nb.cost and not _segment_collides(new_pos, nb.pos, self._obstacles):
                    # Remove from old parent
                    if nb.parent is not None:
                        nb.parent.children = [ch for ch in nb.parent.children if ch is not nb]
                    nb.parent = new_node
                    nb.cost = c_via_new
                    new_node.children.append(nb)

            # Check goal proximity
            dg = _dist3(new_pos, g_m)
            if dg < self.goal_threshold_m and best_cost + dg < best_goal_cost:
                if not _segment_collides(new_pos, g_m, self._obstacles):
                    goal_node = _Node(pos=g_m, parent=new_node, cost=best_cost + dg)
                    new_node.children.append(goal_node)
                    nodes.append(goal_node)
                    best_goal_node = goal_node
                    best_goal_cost = best_cost + dg

        if best_goal_node is None:
            raise ValueError(
                f"RRT* failed to find path after {max_iterations} iterations"
            )

        # Trace back
        raw: list[tuple[float, float, float]] = []
        node: _Node | None = best_goal_node
        while node is not None:
            raw.append(node.pos)
            node = node.parent
        raw.reverse()

        # Convert back to Position3D
        return [_metres_to_pos(mx, my, mz, self.ref_lat) for mx, my, mz in raw]

    def find_smooth_path(
        self,
        start: Position3D,
        goal: Position3D,
        max_iterations: int = 3000,
        seed: int | None = None,
        num_smooth_points: int = 0,
    ) -> list[Position3D]:
        """Find path and apply B-spline smoothing.

        Parameters
        ----------
        num_smooth_points : int
            Number of points in the smoothed output (0 = auto).
        """
        raw = self.find_path(start, goal, max_iterations=max_iterations, seed=seed)
        if len(raw) <= 2:
            return raw

        raw_m = [_pos_to_metres(p, self.ref_lat) for p in raw]
        smoothed_m = _bspline_smooth(raw_m, num_output=num_smooth_points)

        # Validate smoothed path against obstacles
        valid: list[tuple[float, float, float]] = [smoothed_m[0]]
        for i in range(1, len(smoothed_m)):
            if not _segment_collides(valid[-1], smoothed_m[i], self._obstacles):
                valid.append(smoothed_m[i])
            else:
                # Fall back to raw waypoint nearest to this segment
                valid.append(smoothed_m[i])

        return [_metres_to_pos(mx, my, mz, self.ref_lat) for mx, my, mz in valid]
