#include "skymind/rrt_star.h"
#include "skymind/geometry.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <random>
#include <vector>

namespace skymind {

namespace {

struct Vec3 {
    double x, y, z;
};

double dist3(const Vec3& a, const Vec3& b) {
    double dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    return std::sqrt(dx*dx + dy*dy + dz*dz);
}

struct Sphere {
    double cx, cy, floor, ceiling, radius;
};

bool segment_collides(const Vec3& a, const Vec3& b,
                      const std::vector<Sphere>& obs, int samples = 10) {
    for (int t = 0; t <= samples; ++t) {
        double frac = static_cast<double>(t) / samples;
        double px = a.x + (b.x - a.x) * frac;
        double py = a.y + (b.y - a.y) * frac;
        double pz = a.z + (b.z - a.z) * frac;
        for (const auto& o : obs) {
            if (pz >= o.floor && pz <= o.ceiling) {
                double dx = px - o.cx, dy = py - o.cy;
                if (std::sqrt(dx*dx + dy*dy) < o.radius) return true;
            }
        }
    }
    return false;
}

Vec3 pos_to_m(const Position3D& p, double ref_lat) {
    return {
        p.lon * deg_to_m_lon(ref_lat),
        p.lat * DEG_TO_M_LAT,
        p.alt_m
    };
}

Position3D m_to_pos(const Vec3& v, double ref_lat) {
    return {
        v.y / DEG_TO_M_LAT,
        v.x / deg_to_m_lon(ref_lat),
        v.z
    };
}

struct RNode {
    Vec3 pos;
    int parent = -1;
    double cost = 0.0;
};

std::vector<Vec3> bspline_smooth(const std::vector<Vec3>& pts, int num_out, int degree = 3) {
    if (pts.size() <= 2) return pts;
    if (num_out <= 0) num_out = std::max(static_cast<int>(pts.size()) * 3, 20);

    int n = static_cast<int>(pts.size());
    std::vector<Vec3> ctrl;
    for (int i = 0; i < degree; ++i) ctrl.push_back(pts.front());
    for (auto& p : pts) ctrl.push_back(p);
    for (int i = 0; i < degree; ++i) ctrl.push_back(pts.back());
    int m = static_cast<int>(ctrl.size());

    std::vector<Vec3> result(num_out);
    for (int i = 0; i < num_out; ++i) {
        double t = static_cast<double>(i) / (num_out - 1) * (n - 1);
        int seg = std::min(static_cast<int>(t), n - 2);
        double u = t - seg;
        int idx = seg + degree;

        double b0 = (1-u)*(1-u)*(1-u)/6.0;
        double b1 = (3*u*u*u - 6*u*u + 4)/6.0;
        double b2 = (-3*u*u*u + 3*u*u + 3*u + 1)/6.0;
        double b3 = u*u*u/6.0;

        auto clamp = [&](int i_) { return std::max(0, std::min(i_, m-1)); };
        int i0=clamp(idx-1), i1=clamp(idx), i2=clamp(idx+1), i3=clamp(idx+2);

        result[i] = {
            b0*ctrl[i0].x + b1*ctrl[i1].x + b2*ctrl[i2].x + b3*ctrl[i3].x,
            b0*ctrl[i0].y + b1*ctrl[i1].y + b2*ctrl[i2].y + b3*ctrl[i3].y,
            b0*ctrl[i0].z + b1*ctrl[i1].z + b2*ctrl[i2].z + b3*ctrl[i3].z,
        };
    }
    result.front() = pts.front();
    result.back() = pts.back();
    return result;
}

}  // namespace

RRTStarPathfinder::RRTStarPathfinder(
    double step_m, double search_radius_m,
    double altitude_min_m, double altitude_max_m,
    double reference_lat, double goal_threshold_m
)
    : step_m_(step_m), search_radius_m_(search_radius_m)
    , alt_min_(altitude_min_m), alt_max_(altitude_max_m)
    , ref_lat_(reference_lat), goal_threshold_m_(goal_threshold_m)
{
}

void RRTStarPathfinder::set_restricted_zones(const std::vector<RestrictedZone>& zones) {
    zones_ = zones;
}

std::vector<Position3D> RRTStarPathfinder::find_path(
    const Position3D& start, const Position3D& goal,
    int max_iterations, int seed
) const {
    // Build obstacle list in metre space
    std::vector<Sphere> obstacles;
    for (auto& z : zones_) {
        obstacles.push_back({
            z.center_lon * deg_to_m_lon(ref_lat_),
            z.center_lat * DEG_TO_M_LAT,
            z.floor_m, z.ceiling_m, z.radius_m
        });
    }

    Vec3 s_m = pos_to_m(start, ref_lat_);
    Vec3 g_m = pos_to_m(goal, ref_lat_);

    std::mt19937 rng(seed >= 0 ? static_cast<unsigned>(seed) : std::random_device{}());

    std::vector<RNode> nodes;
    nodes.push_back({s_m, -1, 0.0});

    int best_goal_idx = -1;
    double best_goal_cost = std::numeric_limits<double>::infinity();

    double margin = std::max(step_m_ * 5, dist3(s_m, g_m) * 0.3);
    double lo_x = std::min(s_m.x, g_m.x) - margin;
    double hi_x = std::max(s_m.x, g_m.x) + margin;
    double lo_y = std::min(s_m.y, g_m.y) - margin;
    double hi_y = std::max(s_m.y, g_m.y) + margin;

    std::uniform_real_distribution<double> dx(lo_x, hi_x);
    std::uniform_real_distribution<double> dy(lo_y, hi_y);
    std::uniform_real_distribution<double> dz(alt_min_, alt_max_);
    std::uniform_real_distribution<double> d01(0.0, 1.0);

    for (int iter = 0; iter < max_iterations; ++iter) {
        Vec3 rnd;
        if (d01(rng) < 0.2) {
            rnd = g_m;
        } else {
            rnd = {dx(rng), dy(rng), dz(rng)};
        }

        // Nearest
        int nearest_idx = 0;
        double nearest_dist = std::numeric_limits<double>::infinity();
        for (int i = 0; i < static_cast<int>(nodes.size()); ++i) {
            double d = dist3(nodes[i].pos, rnd);
            if (d < nearest_dist) { nearest_dist = d; nearest_idx = i; }
        }
        if (nearest_dist < 1e-9) continue;

        // Steer
        Vec3 new_pos;
        if (nearest_dist > step_m_) {
            double ratio = step_m_ / nearest_dist;
            new_pos = {
                nodes[nearest_idx].pos.x + (rnd.x - nodes[nearest_idx].pos.x) * ratio,
                nodes[nearest_idx].pos.y + (rnd.y - nodes[nearest_idx].pos.y) * ratio,
                nodes[nearest_idx].pos.z + (rnd.z - nodes[nearest_idx].pos.z) * ratio,
            };
        } else {
            new_pos = rnd;
        }
        new_pos.z = std::max(alt_min_, std::min(alt_max_, new_pos.z));

        if (segment_collides(nodes[nearest_idx].pos, new_pos, obstacles)) continue;

        // Find best parent among neighbours
        double new_cost = nodes[nearest_idx].cost + dist3(nodes[nearest_idx].pos, new_pos);
        int best_parent = nearest_idx;
        double best_cost = new_cost;

        std::vector<int> neighbour_idxs;
        for (int i = 0; i < static_cast<int>(nodes.size()); ++i) {
            if (dist3(nodes[i].pos, new_pos) < search_radius_m_) {
                neighbour_idxs.push_back(i);
                double c = nodes[i].cost + dist3(nodes[i].pos, new_pos);
                if (c < best_cost && !segment_collides(nodes[i].pos, new_pos, obstacles)) {
                    best_parent = i;
                    best_cost = c;
                }
            }
        }

        int new_idx = static_cast<int>(nodes.size());
        nodes.push_back({new_pos, best_parent, best_cost});

        // Rewire
        for (int ni : neighbour_idxs) {
            if (ni == best_parent) continue;
            double c_via = best_cost + dist3(new_pos, nodes[ni].pos);
            if (c_via < nodes[ni].cost && !segment_collides(new_pos, nodes[ni].pos, obstacles)) {
                nodes[ni].parent = new_idx;
                nodes[ni].cost = c_via;
            }
        }

        // Goal check
        double dg = dist3(new_pos, g_m);
        if (dg < goal_threshold_m_ && best_cost + dg < best_goal_cost) {
            if (!segment_collides(new_pos, g_m, obstacles)) {
                nodes.push_back({g_m, new_idx, best_cost + dg});
                best_goal_idx = static_cast<int>(nodes.size()) - 1;
                best_goal_cost = best_cost + dg;
            }
        }
    }

    if (best_goal_idx < 0) return {};  // no path

    // Trace back
    std::vector<Vec3> raw;
    int idx = best_goal_idx;
    while (idx >= 0) {
        raw.push_back(nodes[idx].pos);
        idx = nodes[idx].parent;
    }
    std::reverse(raw.begin(), raw.end());

    std::vector<Position3D> result;
    result.reserve(raw.size());
    for (auto& v : raw) result.push_back(m_to_pos(v, ref_lat_));
    return result;
}

std::vector<Position3D> RRTStarPathfinder::find_smooth_path(
    const Position3D& start, const Position3D& goal,
    int max_iterations, int seed, int num_smooth_points
) const {
    auto raw = find_path(start, goal, max_iterations, seed);
    if (raw.size() <= 2) return raw;

    std::vector<Vec3> raw_m;
    for (auto& p : raw) raw_m.push_back(pos_to_m(p, ref_lat_));

    auto smoothed = bspline_smooth(raw_m, num_smooth_points);

    std::vector<Position3D> result;
    result.reserve(smoothed.size());
    for (auto& v : smoothed) result.push_back(m_to_pos(v, ref_lat_));
    return result;
}

}  // namespace skymind
