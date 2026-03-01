cmake_minimum_required(VERSION 3.16)
project(skymind_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Find pybind11
find_package(pybind11 REQUIRED)

# Source files
set(SOURCES
    src/geometry.cpp
    src/astar.cpp
    src/rrt_star.cpp
    src/optimizer.cpp
)

# pybind11 module
pybind11_add_module(skymind_cpp ${SOURCES} bindings/module.cpp)
target_include_directories(skymind_cpp PRIVATE include)

# Install to the Python package directory
install(TARGETS skymind_cpp LIBRARY DESTINATION .)
