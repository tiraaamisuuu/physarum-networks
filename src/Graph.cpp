#include "physarum/Graph.hpp"
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace physarum {
Graph::Graph(std::size_t node_count, std::vector<Edge> edges)
    : node_count_(node_count), edges_(std::move(edges)) {
    if (node_count < 2 || node_count > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::invalid_argument("Graph requires 2..INT_MAX nodes");
    for (const auto& e : edges_) {
        if (e.from >= node_count || e.to >= node_count || e.from == e.to)
            throw std::invalid_argument("Invalid edge endpoints (self-loops are unsupported)");
        if (!std::isfinite(e.length) || e.length <= 0)
            throw std::invalid_argument("Edge lengths must be finite and positive");
    }
}
Graph two_routes() { return Graph(4, {{0,1,1}, {1,3,1}, {0,2,2}, {2,3,2}}); }
}
