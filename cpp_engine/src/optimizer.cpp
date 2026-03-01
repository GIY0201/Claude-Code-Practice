#include "skymind/optimizer.h"

#include <algorithm>
#include <cmath>
#include <vector>

namespace skymind {

namespace {

double point_to_line_distance(const Position3D& p,
                              const Position3D& ls, const Position3D& le) {
    constexpr double M_PER_DEG_LAT = 111320.0;
    double m_per_deg_lon = M_PER_DEG_LAT * std::cos(p.lat * 3.14159265358979 / 180.0);

    double px = (p.lon - ls.lon) * m_per_deg_lon;
    double py = (p.lat - ls.lat) * M_PER_DEG_LAT;
    double pz = p.alt_m - ls.alt_m;

    double lx = (le.lon - ls.lon) * m_per_deg_lon;
    double ly = (le.lat - ls.lat) * M_PER_DEG_LAT;
    double lz = le.alt_m - ls.alt_m;

    double len_sq = lx*lx + ly*ly + lz*lz;
    if (len_sq == 0.0) return std::sqrt(px*px + py*py + pz*pz);

    double t = std::max(0.0, std::min(1.0, (px*lx + py*ly + pz*lz) / len_sq));
    double dx = px - t*lx, dy = py - t*ly, dz = pz - t*lz;
    return std::sqrt(dx*dx + dy*dy + dz*dz);
}

std::vector<Position3D> dp_simplify(const std::vector<Position3D>& path,
                                     double epsilon) {
    if (path.size() <= 2) return path;

    double max_dist = 0.0;
    int max_idx = 0;
    for (int i = 1; i < static_cast<int>(path.size()) - 1; ++i) {
        double d = point_to_line_distance(path[i], path.front(), path.back());
        if (d > max_dist) { max_dist = d; max_idx = i; }
    }

    if (max_dist > epsilon) {
        auto left = dp_simplify(
            std::vector<Position3D>(path.begin(), path.begin() + max_idx + 1), epsilon);
        auto right = dp_simplify(
            std::vector<Position3D>(path.begin() + max_idx, path.end()), epsilon);
        left.pop_back();
        left.insert(left.end(), right.begin(), right.end());
        return left;
    }
    return {path.front(), path.back()};
}

}  // namespace

std::vector<Position3D> smooth_path(
    const std::vector<Position3D>& path,
    double weight_smooth, double weight_data,
    double tolerance, int max_iterations
) {
    if (path.size() <= 2) return path;

    int n = static_cast<int>(path.size());
    // coords[i] = {lat, lon, alt}
    std::vector<std::array<double, 3>> orig(n), sm(n);
    for (int i = 0; i < n; ++i) {
        orig[i] = {path[i].lat, path[i].lon, path[i].alt_m};
        sm[i] = orig[i];
    }

    for (int iter = 0; iter < max_iterations; ++iter) {
        double change = 0.0;
        for (int i = 1; i < n - 1; ++i) {
            for (int j = 0; j < 3; ++j) {
                double old_val = sm[i][j];
                sm[i][j] += weight_data * (orig[i][j] - sm[i][j]);
                sm[i][j] += weight_smooth * (sm[i-1][j] + sm[i+1][j] - 2.0 * sm[i][j]);
                change += std::abs(old_val - sm[i][j]);
            }
        }
        if (change < tolerance) break;
    }

    std::vector<Position3D> result;
    result.reserve(n);
    for (int i = 0; i < n; ++i) {
        result.push_back({sm[i][0], sm[i][1], sm[i][2]});
    }
    return result;
}

std::vector<Position3D> simplify_path(
    const std::vector<Position3D>& path,
    double epsilon_m
) {
    return dp_simplify(path, epsilon_m);
}

}  // namespace skymind
