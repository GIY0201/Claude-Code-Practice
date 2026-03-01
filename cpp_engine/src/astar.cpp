#include "skymind/astar.h"
#include "skymind/geometry.h"

#include <algorithm>
#include <cmath>
#include <queue>
#include <tuple>
#include <unordered_map>
#include <unordered_set>

namespace skymind {

namespace {

using Key = std::tuple<long long, long long, int>;

struct KeyHash {
    size_t operator()(const Key& k) const {
        auto h1 = std::hash<long long>{}(std::get<0>(k));
        auto h2 = std::hash<long long>{}(std::get<1>(k));
        auto h3 = std::hash<int>{}(std::get<2>(k));
        return h1 ^ (h2 << 1) ^ (h3 << 2);
    }
};

Key pos_key(const Position3D& p) {
    return {
        static_cast<long long>(std::round(p.lat * 1e8)),
        static_cast<long long>(std::round(p.lon * 1e8)),
        static_cast<int>(std::round(p.alt_m * 10))
    };
}

struct Node {
    double f_cost;
    double g_cost;
    Position3D position;
    Key parent_key;
    bool has_parent = false;

    bool operator>(const Node& o) const { return f_cost > o.f_cost; }
};

}  // namespace

AStarPathfinder::AStarPathfinder(
    double grid_resolution_m,
    double altitude_step_m,
    double altitude_min_m,
    double altitude_max_m,
    double altitude_change_penalty,
    double reference_lat
)
    : grid_res_(grid_resolution_m)
    , alt_step_(altitude_step_m)
    , alt_min_(altitude_min_m)
    , alt_max_(altitude_max_m)
    , alt_penalty_(altitude_change_penalty)
    , lat_step_(grid_resolution_m / DEG_TO_M_LAT)
    , lon_step_(grid_resolution_m / deg_to_m_lon(reference_lat))
{
}

void AStarPathfinder::set_restricted_zones(const std::vector<RestrictedZone>& zones) {
    restricted_zones_ = zones;
}

bool AStarPathfinder::is_restricted(const Position3D& pos) const {
    for (const auto& z : restricted_zones_) {
        Position3D center{z.center_lat, z.center_lon, 0.0};
        double dist = haversine(pos, center);
        if (dist <= z.radius_m && pos.alt_m >= z.floor_m && pos.alt_m <= z.ceiling_m) {
            return true;
        }
    }
    return false;
}

double AStarPathfinder::heuristic(const Position3D& a, const Position3D& b) const {
    return haversine(a, b) + std::abs(a.alt_m - b.alt_m) * alt_penalty_;
}

Position3D AStarPathfinder::snap_to_grid(const Position3D& pos) const {
    double slat = std::round(pos.lat / lat_step_) * lat_step_;
    double slon = std::round(pos.lon / lon_step_) * lon_step_;
    double salt = std::round((pos.alt_m - alt_min_) / alt_step_) * alt_step_ + alt_min_;
    salt = std::max(alt_min_, std::min(alt_max_, salt));
    return {slat, slon, salt};
}

std::vector<Position3D> AStarPathfinder::find_path(
    const Position3D& start,
    const Position3D& goal,
    int max_iterations
) const {
    Position3D s = snap_to_grid(start);
    Position3D g = snap_to_grid(goal);

    if (is_restricted(s) || is_restricted(g)) return {};

    Key goal_key = pos_key(g);

    std::priority_queue<Node, std::vector<Node>, std::greater<Node>> open;
    std::unordered_set<Key, KeyHash> closed;
    std::unordered_map<Key, double, KeyHash> g_costs;
    std::unordered_map<Key, Key, KeyHash> came_from;

    Key start_key = pos_key(s);
    open.push({heuristic(s, g), 0.0, s, {}, false});
    g_costs[start_key] = 0.0;

    // Store positions for path reconstruction
    std::unordered_map<Key, Position3D, KeyHash> positions;
    positions[start_key] = s;

    static const double dlats[] = {-1, 0, 1};
    static const double dlons[] = {-1, 0, 1};
    static const double dalts[] = {-1, 0, 1};

    int iterations = 0;
    while (!open.empty() && iterations < max_iterations) {
        ++iterations;
        Node current = open.top();
        open.pop();
        Key ck = pos_key(current.position);

        if (ck == goal_key) {
            // Reconstruct path
            std::vector<Position3D> path;
            Key k = ck;
            while (true) {
                path.push_back(positions[k]);
                auto it = came_from.find(k);
                if (it == came_from.end()) break;
                k = it->second;
            }
            std::reverse(path.begin(), path.end());
            path.front() = start;
            path.back() = goal;
            return path;
        }

        if (closed.count(ck)) continue;
        closed.insert(ck);

        // 26-directional neighbours
        for (double di : dlats) {
            for (double dj : dlons) {
                for (double dk : dalts) {
                    if (di == 0 && dj == 0 && dk == 0) continue;
                    double new_alt = current.position.alt_m + dk * alt_step_;
                    if (new_alt < alt_min_ || new_alt > alt_max_) continue;

                    Position3D nb{
                        current.position.lat + di * lat_step_,
                        current.position.lon + dj * lon_step_,
                        new_alt
                    };

                    Key nk = pos_key(nb);
                    if (closed.count(nk)) continue;
                    if (is_restricted(nb)) continue;

                    double move = distance_3d(current.position, nb);
                    double alt_change = std::abs(nb.alt_m - current.position.alt_m);
                    double new_g = current.g_cost + move + alt_change * alt_penalty_;

                    auto it = g_costs.find(nk);
                    if (it == g_costs.end() || new_g < it->second) {
                        g_costs[nk] = new_g;
                        double f = new_g + heuristic(nb, g);
                        open.push({f, new_g, nb, ck, true});
                        came_from[nk] = ck;
                        positions[nk] = nb;
                    }
                }
            }
        }
    }

    return {};  // no path found
}

}  // namespace skymind
