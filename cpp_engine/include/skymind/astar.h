#pragma once

#include "types.h"
#include <vector>

namespace skymind {

class AStarPathfinder {
public:
    AStarPathfinder(
        double grid_resolution_m = 100.0,
        double altitude_step_m = 10.0,
        double altitude_min_m = 30.0,
        double altitude_max_m = 400.0,
        double altitude_change_penalty = 2.0,
        double reference_lat = 37.5665
    );

    void set_restricted_zones(const std::vector<RestrictedZone>& zones);
    bool is_restricted(const Position3D& pos) const;

    std::vector<Position3D> find_path(
        const Position3D& start,
        const Position3D& goal,
        int max_iterations = 50000
    ) const;

private:
    double grid_res_;
    double alt_step_;
    double alt_min_;
    double alt_max_;
    double alt_penalty_;
    double lat_step_;
    double lon_step_;
    std::vector<RestrictedZone> restricted_zones_;

    double heuristic(const Position3D& a, const Position3D& b) const;
    Position3D snap_to_grid(const Position3D& pos) const;
};

}  // namespace skymind
