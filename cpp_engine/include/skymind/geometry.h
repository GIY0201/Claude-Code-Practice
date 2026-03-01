#pragma once

#include "types.h"

namespace skymind {

constexpr double EARTH_RADIUS_M = 6'371'000.0;
constexpr double DEG_TO_M_LAT = 111'320.0;
constexpr double PI = 3.14159265358979323846;

inline double deg_to_rad(double deg) { return deg * PI / 180.0; }

/// Haversine horizontal distance in metres.
double haversine(const Position3D& a, const Position3D& b);

/// 3-D distance (Haversine horizontal + vertical).
double distance_3d(const Position3D& a, const Position3D& b);

/// Metres per degree of longitude at given latitude.
double deg_to_m_lon(double lat);

}  // namespace skymind
