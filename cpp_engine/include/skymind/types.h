#pragma once

#include <cmath>
#include <vector>
#include <string>

namespace skymind {

struct Position3D {
    double lat = 0.0;
    double lon = 0.0;
    double alt_m = 0.0;

    Position3D() = default;
    Position3D(double lat_, double lon_, double alt_m_)
        : lat(lat_), lon(lon_), alt_m(alt_m_) {}
};

struct Velocity3D {
    double vx = 0.0;
    double vy = 0.0;
    double vz = 0.0;
};

struct RestrictedZone {
    double center_lat = 0.0;
    double center_lon = 0.0;
    double radius_m = 0.0;
    double floor_m = 0.0;
    double ceiling_m = 999999.0;
};

}  // namespace skymind
