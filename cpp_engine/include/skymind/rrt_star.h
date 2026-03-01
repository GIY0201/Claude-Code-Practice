#pragma once

#include "types.h"
#include <vector>
#include <optional>

namespace skymind {

class RRTStarPathfinder {
public:
    RRTStarPathfinder(
        double step_m = 200.0,
        double search_radius_m = 500.0,
        double altitude_min_m = 30.0,
        double altitude_max_m = 400.0,
        double reference_lat = 37.5665,
        double goal_threshold_m = 150.0
    );

    void set_restricted_zones(const std::vector<RestrictedZone>& zones);

    std::vector<Position3D> find_path(
        const Position3D& start,
        const Position3D& goal,
        int max_iterations = 3000,
        int seed = -1
    ) const;

    std::vector<Position3D> find_smooth_path(
        const Position3D& start,
        const Position3D& goal,
        int max_iterations = 3000,
        int seed = -1,
        int num_smooth_points = 0
    ) const;

private:
    double step_m_;
    double search_radius_m_;
    double alt_min_;
    double alt_max_;
    double ref_lat_;
    double goal_threshold_m_;
    std::vector<RestrictedZone> zones_;
};

}  // namespace skymind
