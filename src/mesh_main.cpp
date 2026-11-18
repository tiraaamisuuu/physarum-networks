#include "physarum/SparseFlowSolver.hpp"
#include "physarum/PhysarumModel.hpp"
#include <bit>
#include <charconv>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#ifndef PHYSARUM_SOURCE_FINGERPRINT
#define PHYSARUM_SOURCE_FINGERPRINT "untracked"
#endif

namespace {
constexpr const char* diagnostic_header =
    "step,time,source,sink,conservation_inf,backward_error,scaled_rcond_estimate\n";

template<class T> T number(const std::string& text) {
    T value{};
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (error != std::errc{} || end != text.data() + text.size())
        throw std::invalid_argument("Invalid mesh number: " + text);
    return value;
}

std::vector<std::string> row(const std::string& line) {
    std::vector<std::string> values;
    std::string clean = line;
    if (!clean.empty() && clean.back() == '\r') clean.pop_back();
    std::istringstream stream(clean);
    std::string value;
    while (std::getline(stream, value, ',')) values.push_back(value);
    if (!clean.empty() && clean.back() == ',') values.emplace_back();
    return values;
}

std::ifstream input(const std::filesystem::path& path, const std::string& header) {
    std::ifstream stream(path);
    std::string line;
    if (!std::getline(stream, line)) throw std::invalid_argument("Cannot read mesh CSV: " + path.string());
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line != header)
        throw std::invalid_argument("Invalid mesh CSV header: " + path.string());
    return stream;
}

std::ofstream output(const std::filesystem::path& path, bool binary = false) {
    std::ofstream stream(path, binary ? (std::ios::out | std::ios::binary) : std::ios::out);
    stream.exceptions(std::ios::failbit | std::ios::badbit);
    stream << std::setprecision(17);
    return stream;
}

void write(std::ofstream& stream, const std::vector<double>& values) {
    stream.write(reinterpret_cast<const char*>(values.data()),
                 static_cast<std::streamsize>(values.size() * sizeof(double)));
}

void write_diagnostic(std::ofstream& stream, std::size_t step, double time,
                      std::pair<std::size_t, std::size_t> pair,
                      const physarum::FlowResult& state) {
    stream << step << ',' << time << ',' << pair.first << ',' << pair.second << ','
           << state.conservation_inf << ',' << state.backward_error << ','
           << state.scaled_rcond << '\n';
}

void positive(double value) {
    if (!std::isfinite(value) || value <= 0)
        throw std::runtime_error("Mesh conductivity underflow/overflow; no floor is applied");
}
}

int main(int argc, char** argv) {
    try {
        if (argc != 7)
            throw std::invalid_argument("Usage: physarum_mesh CONFIG EDGES_CSV NODE_COUNT INITIAL_D_CSV DEMANDS_CSV OUTPUT_DIRECTORY");
        static_assert(std::endian::native == std::endian::little && sizeof(double) == 8
                      && std::numeric_limits<double>::is_iec559);

        std::ifstream config(argv[1]);
        std::string line;
        std::map<std::string, std::string> options;
        if (!config) throw std::invalid_argument("Cannot read mesh config");
        while (std::getline(config, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            const auto at = line.find('=');
            if (at == std::string::npos ||
                !options.emplace(line.substr(0, at), line.substr(at + 1)).second)
                throw std::invalid_argument("Mesh config needs unique key=value lines");
        }
        for (const auto& [key, value] : options) {
            (void)value;
            if (key != "dt" && key != "steps" && key != "gamma" &&
                key != "current" && key != "integrator")
                throw std::invalid_argument("Unknown mesh config key: " + key);
        }
        if (options.size() != 4 && options.size() != 5)
            throw std::invalid_argument("Mesh config needs dt, steps, gamma, current, and optional integrator");
        const double dt = number<double>(options.at("dt"));
        const double gamma = number<double>(options.at("gamma"));
        const double current = number<double>(options.at("current"));
        const auto steps = number<std::size_t>(options.at("steps"));
        const auto nodes = number<std::size_t>(argv[3]);
        const std::string integrator = options.contains("integrator") ? options.at("integrator") : "euler";
        if (integrator != "euler" && integrator != "heun")
            throw std::invalid_argument("Mesh integrator must be euler or heun");
        if (!std::isfinite(dt) || dt <= 0 || dt > .25 || !std::isfinite(gamma) ||
            gamma <= 0 || !std::isfinite(current) || current <= 0 || steps < 1 ||
            steps > 6000 || nodes < 2 || nodes > 8000)
            throw std::invalid_argument("Unsupported mesh dimensions or parameters");

        std::vector<physarum::Edge> edges;
        auto graph_csv = input(argv[2], "edge,from,to,length");
        while (std::getline(graph_csv, line)) {
            if (edges.size() >= 25000) throw std::invalid_argument("Mesh exceeds 25000 edges");
            const auto values = row(line);
            if (values.size() != 4 || number<std::size_t>(values[0]) != edges.size())
                throw std::invalid_argument("Invalid mesh edge ordering");
            edges.push_back({number<std::size_t>(values[1]), number<std::size_t>(values[2]),
                             number<double>(values[3])});
        }
        if (edges.empty() || edges.size() > 25000 || edges.size() * (steps + 1) > 25000000)
            throw std::invalid_argument("Mesh output size exceeds supported bound");
        physarum::Graph graph(nodes, std::move(edges));
        std::vector<double> d;
        auto initial = input(argv[4], "edge,conductivity");
        while (std::getline(initial, line)) {
            if (d.size() >= graph.edges().size()) throw std::invalid_argument("Too many initial conductivities");
            const auto values = row(line);
            if (values.size() != 2 || number<std::size_t>(values[0]) != d.size())
                throw std::invalid_argument("Invalid initial mesh conductivities");
            const double value = number<double>(values[1]);
            if (!std::isfinite(value) || value <= 0)
                throw std::invalid_argument("Initial mesh D must be positive");
            d.push_back(value);
        }
        if (d.size() != graph.edges().size())
            throw std::invalid_argument("Initial mesh D count mismatch");

        std::vector<std::pair<std::size_t, std::size_t>> pairs;
        auto demand = input(argv[5], "step,source,sink");
        while (std::getline(demand, line)) {
            if (pairs.size() > steps) throw std::invalid_argument("Too many mesh demand states");
            const auto values = row(line);
            if (values.size() != 3 || number<std::size_t>(values[0]) != pairs.size())
                throw std::invalid_argument("Invalid demand ordering");
            const auto source = number<std::size_t>(values[1]);
            const auto sink = number<std::size_t>(values[2]);
            if (source >= nodes || sink >= nodes || source == sink)
                throw std::invalid_argument("Invalid mesh terminal pair");
            pairs.emplace_back(source, sink);
        }
        if (pairs.size() != steps + 1)
            throw std::invalid_argument("Mesh demands require steps+1 states");

        physarum::SparseFlowSolver solver(graph);
        const std::filesystem::path folder = argv[6];
        if (std::filesystem::exists(folder) && !std::filesystem::is_empty(folder))
            throw std::invalid_argument("Mesh output directory must be new or empty; existing records are never overwritten");
        std::filesystem::create_directories(folder);
        auto ds = output(folder / "D.f64", true);
        auto qs = output(folder / "Q.f64", true);
        auto ps = output(folder / "P.f64", true);
        auto diagnostics = output(folder / "diagnostics.csv");
        diagnostics << diagnostic_header;
        std::ofstream stage_q, stage_p, stage_diagnostics;
        if (integrator == "heun") {
            stage_q = output(folder / "stage_Q.f64", true);
            stage_p = output(folder / "stage_P.f64", true);
            stage_diagnostics = output(folder / "stage_diagnostics.csv");
            stage_diagnostics << diagnostic_header;
        }

        for (std::size_t step = 0; step <= steps; ++step) {
            const auto state = solver.solve(d, pairs[step].first, pairs[step].second, current);
            write(ds, d);
            write(qs, state.flows);
            write(ps, state.pressures);
            write_diagnostic(diagnostics, step, static_cast<double>(step) * dt, pairs[step], state);
            if (step == steps) break;

            if (integrator == "euler") {
                // Preserve the original Euler operation order for legacy replay.
                for (std::size_t k = 0; k < d.size(); ++k) {
                    const double next = (1 - dt) * d[k] + dt * physarum::reinforcement(state.flows[k], gamma);
                    positive(next);
                    d[k] = next;
                }
            } else {
                // Heun / SSPRK2: two Euler stages and their convex average.
                // Both stages use the same held pair, including at a switch boundary.
                std::vector<double> predictor(d.size());
                for (std::size_t k = 0; k < d.size(); ++k) {
                    predictor[k] = (1 - dt) * d[k] + dt * physarum::reinforcement(state.flows[k], gamma);
                    positive(predictor[k]);
                }
                const auto predicted = solver.solve(predictor, pairs[step].first, pairs[step].second, current);
                write(stage_q, predicted.flows);
                write(stage_p, predicted.pressures);
                write_diagnostic(stage_diagnostics, step, static_cast<double>(step + 1) * dt,
                                 pairs[step], predicted);
                for (std::size_t k = 0; k < d.size(); ++k) {
                    const double second = (1 - dt) * predictor[k] + dt * physarum::reinforcement(predicted.flows[k], gamma);
                    positive(second);
                    const double next = .5 * d[k] + .5 * second;
                    positive(next);
                    d[k] = next;
                }
            }
        }
        auto metadata = output(folder / "metadata.txt");
        metadata << "model=Tero_2010_sigmoid_mesh_v1\nsolver=Eigen_SimplicialLDLT_diagonally_scaled"
                 << "\npressure_reference=node_0\ncondition_diagnostic=Hager_inverse_1_norm_estimate_6_iterations"
                 << "\nintegrator=" << integrator << "\ncompiler=" << __VERSION__
                 << "\nengine_source_fingerprint=" << PHYSARUM_SOURCE_FINGERPRINT
                 << "\neigen=" << EIGEN_WORLD_VERSION << '.' << EIGEN_MAJOR_VERSION << '.' << EIGEN_MINOR_VERSION
                 << "\npruning=none\nconductivity_floor=none\nformat=IEEE754_float64_little_endian\n";
        ds.close(); qs.close(); ps.close(); diagnostics.close(); metadata.close();
        if (integrator == "heun") { stage_q.close(); stage_p.close(); stage_diagnostics.close(); }
        std::cout << "Completed " << steps << " " << integrator << " updates, " << nodes
                  << " nodes, " << graph.edges().size() << " edges\n";
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
