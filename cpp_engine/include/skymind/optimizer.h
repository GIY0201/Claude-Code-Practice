#pragma once

#include "types.h"
#include <vector>

namespace skymind {

/// Gradient-descent path smoothing (start/end fixed).
std::vector<Position3D> smooth_path(
    const std::vector<Position3D>& path,
    double weight_smooth = 0.3,
    double weight_data = 0.5,
    double tolerance = 0.00001,
    int max_iterations = 100
);

/// Douglas-Peucker path simplification.
std::vector<Position3D> simplify_path(
    const std::vector<Position3D>& path,
    double epsilon_m = 10.0
);

}  // namespace skymind
