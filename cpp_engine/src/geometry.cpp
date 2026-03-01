#include "skymind/geometry.h"
#include <cmath>

namespace skymind {

double haversine(const Position3D& a, const Position3D& b) {
    double dlat = deg_to_rad(b.lat - a.lat);
    double dlon = deg_to_rad(b.lon - a.lon);
    double la = deg_to_rad(a.lat);
    double lb = deg_to_rad(b.lat);
    double h = std::sin(dlat / 2) * std::sin(dlat / 2) +
               std::cos(la) * std::cos(lb) *
               std::sin(dlon / 2) * std::sin(dlon / 2);
    return 2.0 * EARTH_RADIUS_M * std::asin(std::sqrt(h));
}

double distance_3d(const Position3D& a, const Position3D& b) {
    double horiz = haversine(a, b);
    double dz = b.alt_m - a.alt_m;
    return std::sqrt(horiz * horiz + dz * dz);
}

double deg_to_m_lon(double lat) {
    return DEG_TO_M_LAT * std::cos(deg_to_rad(lat));
}

}  // namespace skymind
