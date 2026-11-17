#!/usr/bin/env python3
"""Run the C++ fixture, independently check its CSV, and plot measured results."""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run(executable, name, dt, duration, root):
    directory = root / name
    config = root / f"{name}.cfg"
    steps = round(duration / dt)
    assert abs(steps * dt - duration) < 1e-12
    config.write_text(f"dt={dt}\nsteps={steps}\ngamma=1.8\ncurrent=2.0\n"
                      "initial_conductivity=0.5\nsource=0\nsink=3\n")
    subprocess.run([str(executable), str(config), str(directory)], check=True, capture_output=True, text=True)
    data = np.genfromtxt(directory / "history.csv", delimiter=",", names=True)
    return directory, data


def check_fixture(data, dt):
    d = data["conductivity"].reshape(-1, 4)
    q = data["flow"].reshape(-1, 4)
    # Independent circuit reduction: sum edge resistances within each route.
    resistance = np.column_stack((1/d[:, 0] + 1/d[:, 1], 2/d[:, 2] + 2/d[:, 3]))
    voltage = 2 / (1/resistance[:, 0] + 1/resistance[:, 1])
    route_flow = voltage[:, None] / resistance
    exact_q = route_flow[:, [0, 0, 1, 1]]
    exact_from = np.column_stack((voltage, route_flow[:, 0]/d[:, 1],
                                 voltage, 2*route_flow[:, 1]/d[:, 3]))
    flow_error = float(np.max(np.abs(q-exact_q)))
    pressure_error = float(np.max(np.abs(data["pressure_from"].reshape(-1, 4)-exact_from)))
    power = np.abs(q[:-1])**1.8
    expected = (1-dt)*d[:-1] + dt*power/(1+power)
    euler_error = float(np.max(np.abs(d[1:]-expected)))
    assert flow_error < 2e-12 and pressure_error < 2e-11 and euler_error < 2e-15
    assert np.all(d > 0) and np.all(d <= 1)
    return {"analytic_flow_max_abs_error": flow_error,
            "analytic_pressure_max_abs_error": pressure_error,
            "euler_update_max_abs_error": euler_error,
            "max_conservation_inf": float(data["conservation_inf"].max()),
            "max_backward_error": float(data["backward_error"].max()),
            "min_scaled_rcond": float(data["scaled_rcond"].min())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=ROOT/"build/physarum_run")
    parser.add_argument("--output", type=Path, default=ROOT/"results/phase1")
    args = parser.parse_args()
    exe = args.executable.resolve()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    base_dir, base = run(exe, "baseline", .05, 30, root)
    repeat_dir, _ = run(exe, "repeat", .05, 30, root)
    for filename in ("history.csv", "edges.csv", "config.cfg", "summary.txt", "metadata.txt"):
        assert (base_dir/filename).read_bytes() == (repeat_dir/filename).read_bytes(), filename
    report = check_fixture(base, .05)
    report["deterministic_outputs_byte_identical"] = True
    # Check the command-line boundary as well as the simulation.
    bad_cases = {"unknown": "unknown=1\n", "duplicate": "dt=.1\n", "nan": ""}
    text = (root/"baseline.cfg").read_text()
    for name, suffix in bad_cases.items():
        config = root/f"invalid_{name}.cfg"
        config.write_text(text.replace("dt=0.05", "dt=nan") if name == "nan" else text+suffix)
        result = subprocess.run([str(exe), str(config), str(root/f"invalid_{name}")], capture_output=True)
        assert result.returncode != 0 and not (root/f"invalid_{name}").exists()
        config.unlink()
    report["invalid_cli_configurations_rejected"] = list(bad_cases)
    _, ref = run(exe, "reference", .000625, 4, root)
    reference = ref["conductivity"][-4:]
    refinements = []
    for dt in (.1, .05, .025, .0125):
        _, data = run(exe, f"dt_{dt}", dt, 4, root)
        check_fixture(data, dt)
        error = float(np.max(np.abs(data["conductivity"][-4:]-reference)))
        refinements.append({"dt": dt, "error_at_t4": error})
    for a, b in zip(refinements, refinements[1:]):
        a["error_ratio_to_next"] = a["error_at_t4"]/b["error_at_t4"]
        assert 1.8 < a["error_ratio_to_next"] < 2.3
    _, half = run(exe, "half_step", .025, 30, root)
    d = base["conductivity"].reshape(-1, 4)
    q = base["flow"].reshape(-1, 4)
    expected_limit = 2**1.8/(1+2**1.8)
    report.update({"parameters": {"dt": .05, "gamma": 1.8, "current": 2, "duration": 30},
                   "initial_pressures": [16/3, 8/3, 8/3, 0],
                   "final_conductivities": d[-1].tolist(),
                   "final_signed_flows": q[-1].tolist(),
                   "short_route_length": 2, "long_route_length": 4,
                   "single_route_equilibrium_conductivity": expected_limit,
                   "final_short_route_limit_error": abs(float(d[-1, 0])-expected_limit),
                   "max_trajectory_dt_halving_difference": float(np.max(np.abs(d-half["conductivity"].reshape(-1, 4)[::2]))),
                   "timestep_study_reference_dt": .000625, "timestep_study": refinements,
                   "python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__,
                   "platform": platform.platform(), "binary_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()})
    # Hash all implementation, build and fixture inputs; no dependency on a Git commit.
    files = [ROOT/"CMakeLists.txt", Path(__file__), ROOT/"experiments/configs/two_routes.cfg"]
    for folder in ("include", "src", "tests"):
        files += sorted((ROOT/folder).rglob("*.hpp")) + sorted((ROOT/folder).rglob("*.cpp"))
    report["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (root/"validation.json").write_text(json.dumps(report, indent=2)+"\n")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout="constrained")
    fig.suptitle("Physarum flow adaptation | Phase 1 numerical fixture", fontsize=16, fontweight="bold")
    t = base["time"].reshape(-1, 4)[:, 0]
    ax = axes[0]
    ax.plot(t, d[:, 0], color="#007c83", lw=2.5, label="Short route (L=2): edges 0, 1")
    ax.plot(t, d[:, 2], color="#c85b28", lw=2.5, label="Long route (L=4): edges 2, 3")
    ax.axhline(expected_limit, color="#7a8690", ls="--", lw=1, label=f"Single-route equilibrium: {expected_limit:.4f}")
    ax.set(xlabel="Time (arbitrary model units)", ylabel="Conductivity D", ylim=(-.025, .85),
           title="Short route gains flow; long route decays")
    ax.legend(loc="center right", fontsize=8, frameon=False)
    ax.grid(alpha=.15)
    ax.text(.25,.05,"Fixed source 0 → sink 3  |  I₀=2, γ=1.8, Δt=0.05\nPaired edges overlap by symmetry. No pruning.",
            transform=ax.transAxes, fontsize=8, color="#53616b")
    ax = axes[1]
    xs = np.array([r["dt"] for r in refinements]); ys = np.array([r["error_at_t4"] for r in refinements])
    ax.loglog(xs, ys, "o-", color="#324c81", lw=2, label="Measured error at t=4")
    ax.loglog(xs, ys[0]*xs/xs[0], "--", color="#8d98a5", label="First-order slope (∝ Δt)")
    ax.set(xlabel="Euler time step Δt", ylabel="Maximum absolute error in D",
           title="Smaller time steps reduce transient error")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(which="both", alpha=.15)
    ax.text(.03,.94,"Reference: Δt=0.000625\nNumerical comparison; not an exact solution", va="top",
            transform=ax.transAxes, fontsize=8, color="#53616b")
    fig.savefig(root/"conductivity.png", dpi=180)
    fig.savefig(root/"conductivity.svg")
    plt.close(fig)
    (root/"REPORT.md").write_text(
        "# Phase 1 measured validation\n\nGenerated by `analysis/run_validation.py`. Full data: `validation.json`.\n\n"
        f"- Repeated outputs byte-identical: yes.\n- Maximum conservation residual: {report['max_conservation_inf']:.6g}.\n"
        f"- Maximum pressure backward error: {report['max_backward_error']:.6g}.\n"
        f"- Maximum independent analytic flow error: {report['analytic_flow_max_abs_error']:.6g}.\n"
        f"- Maximum independent analytic pressure error: {report['analytic_pressure_max_abs_error']:.6g}.\n"
        f"- Maximum CSV Euler update error: {report['euler_update_max_abs_error']:.6g}.\n"
        f"- Final conductivities: {report['final_conductivities']}.\n"
        f"- Final signed flows: {report['final_signed_flows']}.\n"
        f"- Predicted single-route equilibrium D: {expected_limit:.12g}.\n"
        f"- Maximum trajectory change on halving dt: {report['max_trajectory_dt_halving_difference']:.6g}.\n\n"
        "| dt | Error at t=4 vs fine Euler reference | Ratio to next |\n|---|---|---|\n"+
        "".join(f"| {r['dt']} | {r['error_at_t4']:.8g} | "+
                (f"{r['error_ratio_to_next']:.5g}" if 'error_ratio_to_next' in r else "—")+" |\n" for r in refinements)+
        "\nThe reference has finite discretisation error. First-order refinement is observed for this fixture. "
        "The last ratio is undefined. Late equilibrium agreement does not establish transient accuracy. "
        "This experiment neither replicates Figure 4 nor establishes general shortest-path convergence.\n")
    print(json.dumps({k:v for k,v in report.items() if k != "source_sha256"}, indent=2))


if __name__ == "__main__":
    main()
