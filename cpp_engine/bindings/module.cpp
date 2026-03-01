#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "skymind/types.h"
#include "skymind/geometry.h"
#include "skymind/astar.h"
#include "skymind/rrt_star.h"
#include "skymind/optimizer.h"

namespace py = pybind11;

PYBIND11_MODULE(skymind_cpp, m) {
    m.doc() = "SkyMind C++ path engine with pybind11 bindings";

    // ── types ────────────────────────────────────────────────────────
    py::class_<skymind::Position3D>(m, "Position3D")
        .def(py::init<double, double, double>(),
             py::arg("lat") = 0.0, py::arg("lon") = 0.0, py::arg("alt_m") = 0.0)
        .def_readwrite("lat", &skymind::Position3D::lat)
        .def_readwrite("lon", &skymind::Position3D::lon)
        .def_readwrite("alt_m", &skymind::Position3D::alt_m)
        .def("__repr__", [](const skymind::Position3D& p) {
            return "Position3D(lat=" + std::to_string(p.lat) +
                   ", lon=" + std::to_string(p.lon) +
                   ", alt_m=" + std::to_string(p.alt_m) + ")";
        });

    py::class_<skymind::RestrictedZone>(m, "RestrictedZone")
        .def(py::init<>())
        .def_readwrite("center_lat", &skymind::RestrictedZone::center_lat)
        .def_readwrite("center_lon", &skymind::RestrictedZone::center_lon)
        .def_readwrite("radius_m", &skymind::RestrictedZone::radius_m)
        .def_readwrite("floor_m", &skymind::RestrictedZone::floor_m)
        .def_readwrite("ceiling_m", &skymind::RestrictedZone::ceiling_m);

    // ── geometry ─────────────────────────────────────────────────────
    m.def("haversine", &skymind::haversine, "Haversine distance in metres",
          py::arg("a"), py::arg("b"));
    m.def("distance_3d", &skymind::distance_3d, "3-D distance in metres",
          py::arg("a"), py::arg("b"));

    // ── A* ───────────────────────────────────────────────────────────
    py::class_<skymind::AStarPathfinder>(m, "AStarPathfinder")
        .def(py::init<double, double, double, double, double, double>(),
             py::arg("grid_resolution_m") = 100.0,
             py::arg("altitude_step_m") = 10.0,
             py::arg("altitude_min_m") = 30.0,
             py::arg("altitude_max_m") = 400.0,
             py::arg("altitude_change_penalty") = 2.0,
             py::arg("reference_lat") = 37.5665)
        .def("set_restricted_zones", &skymind::AStarPathfinder::set_restricted_zones)
        .def("is_restricted", &skymind::AStarPathfinder::is_restricted)
        .def("find_path", &skymind::AStarPathfinder::find_path,
             py::arg("start"), py::arg("goal"), py::arg("max_iterations") = 50000);

    // ── RRT* ─────────────────────────────────────────────────────────
    py::class_<skymind::RRTStarPathfinder>(m, "RRTStarPathfinder")
        .def(py::init<double, double, double, double, double, double>(),
             py::arg("step_m") = 200.0,
             py::arg("search_radius_m") = 500.0,
             py::arg("altitude_min_m") = 30.0,
             py::arg("altitude_max_m") = 400.0,
             py::arg("reference_lat") = 37.5665,
             py::arg("goal_threshold_m") = 150.0)
        .def("set_restricted_zones", &skymind::RRTStarPathfinder::set_restricted_zones)
        .def("find_path", &skymind::RRTStarPathfinder::find_path,
             py::arg("start"), py::arg("goal"),
             py::arg("max_iterations") = 3000, py::arg("seed") = -1)
        .def("find_smooth_path", &skymind::RRTStarPathfinder::find_smooth_path,
             py::arg("start"), py::arg("goal"),
             py::arg("max_iterations") = 3000, py::arg("seed") = -1,
             py::arg("num_smooth_points") = 0);

    // ── optimizer ────────────────────────────────────────────────────
    m.def("smooth_path", &skymind::smooth_path,
          py::arg("path"),
          py::arg("weight_smooth") = 0.3,
          py::arg("weight_data") = 0.5,
          py::arg("tolerance") = 0.00001,
          py::arg("max_iterations") = 100);
    m.def("simplify_path", &skymind::simplify_path,
          py::arg("path"),
          py::arg("epsilon_m") = 10.0);
}
