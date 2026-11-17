"""Read and run the Phase 1 C++ experiment, independent of the GUI toolkit."""
from dataclasses import dataclass
import csv
import io
import math
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {"current": 2.0, "gamma": 1.8, "dt": 0.05, "duration": 30.0,
            "initial_conductivity": 0.5}
REQUIRED = ("history.csv", "edges.csv", "config.cfg")
FILES = (*REQUIRED, "metadata.txt", "summary.txt")


@dataclass
class RunData:
    parameters: dict
    edges: list
    frames: list
    files: dict
    origin: str


def validate_parameters(payload):
    bounds = {"current": (0.1, 5), "gamma": (0.5, 3), "dt": (0.005, 0.25),
              "duration": (1, 60), "initial_conductivity": (0.01, 1)}
    if not isinstance(payload, dict) or set(payload) != set(bounds):
        raise ValueError("Expected current, gamma, dt, duration and initial_conductivity.")
    result = {}
    for key, (low, high) in bounds.items():
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number.")
        if not low <= value <= high:
            raise ValueError(f"{key} must be between {low:g} and {high:g}.")
        result[key] = float(value)
    steps = round(result["duration"] / result["dt"])
    if not math.isclose(steps*result["dt"], result["duration"], abs_tol=1e-9):
        raise ValueError("Duration must be a whole multiple of the time step.")
    result.update(steps=steps, source=0, sink=3)
    return result


def decode_run(files, origin):
    if not all(name in files for name in REQUIRED):
        raise ValueError("Run needs history.csv, edges.csv and config.cfg.")
    config = {}
    for line in files["config.cfg"].decode().splitlines():
        line = line.split("#")[0].strip()
        if line:
            key, value = line.split("=", 1)
            if key.strip() in config:
                raise ValueError("Duplicate configuration key.")
            config[key.strip()] = float(value.strip())
    for key in ("dt", "steps", "current", "gamma", "source", "sink", "initial_conductivity"):
        if key not in config or not math.isfinite(config[key]):
            raise ValueError(f"Missing or nonfinite configuration value: {key}.")
    if config["steps"] < 1 or config["steps"] != int(config["steps"]) or not 0 < config["dt"] <= 1:
        raise ValueError("Invalid step count or time step.")
    if config["steps"] > 12000:
        raise ValueError("This small-fixture viewer accepts at most 12,000 updates per run.")
    if config["current"] <= 0 or config["gamma"] <= 0 or config["initial_conductivity"] < 0:
        raise ValueError("Invalid current, response exponent or initial conductivity.")
    if (config["source"] not in range(4) or config["sink"] not in range(4) or
        config["source"] == config["sink"]):
        raise ValueError("Invalid source and sink.")
    if {config["source"],config["sink"]} != {0,3}:
        raise ValueError("This viewer supports the terminal pair 0 and 3, in either direction.")
    config["steps"] = int(config["steps"])
    config["duration"] = config["dt"] * config["steps"]
    edges = [{"id": int(r["edge"]), "from": int(r["from"]), "to": int(r["to"]),
              "length": float(r["length"])} for r in csv.DictReader(io.StringIO(files["edges.csv"].decode()))]
    if (len(edges) != 4 or [e["id"] for e in edges] != list(range(4)) or
        [(e["from"],e["to"]) for e in edges] != [(0,1),(1,3),(0,2),(2,3)] or
        any(not math.isfinite(e["length"]) or e["length"] <= 0 for e in edges)):
        raise ValueError("This viewer supports the Phase 1 four-node, two-route fixture.")
    rows = list(csv.DictReader(io.StringIO(files["history.csv"].decode())))
    if len(rows) != (config["steps"]+1)*4:
        raise ValueError("History row count does not match the recorded configuration.")
    frames = []
    for start in range(0, len(rows), 4):
        group = rows[start:start+4]
        step = start//4
        time = float(group[0]["time"])
        if not math.isfinite(time) or not math.isclose(time, step*config["dt"], abs_tol=1e-9):
            raise ValueError("History times do not match the integration steps.")
        pressures = [None]*4
        d, q = [], []
        diagnostics = []
        for edge, row in zip(edges, group):
            if int(row["edge"]) != edge["id"] or int(row["step"]) != step or float(row["time"]) != time:
                raise ValueError("History has inconsistent edge, step or time ordering.")
            values = {key: float(row[key]) for key in ("conductivity", "flow", "pressure_from", "pressure_to",
                                                       "conservation_inf", "backward_error", "scaled_rcond")}
            if not all(math.isfinite(value) for value in values.values()) or values["conductivity"] < 0:
                raise ValueError("History contains nonfinite or negative conductivity values.")
            expected = values["conductivity"]/edge["length"]*(values["pressure_from"]-values["pressure_to"])
            if not math.isfinite(expected) or not math.isclose(expected,values["flow"],rel_tol=1e-10,abs_tol=1e-12):
                raise ValueError("History flow does not agree with D/L times the pressure difference.")
            if values["conservation_inf"] < 0 or values["backward_error"] < 0 or not 0 < values["scaled_rcond"] <= 1:
                raise ValueError("Invalid solver diagnostics.")
            for node, key in ((edge["from"],"pressure_from"), (edge["to"],"pressure_to")):
                if pressures[node] is not None and not math.isclose(pressures[node],values[key],rel_tol=1e-10,abs_tol=1e-12):
                    raise ValueError("Conflicting node pressures in the history.")
                pressures[node] = values[key]
            d.append(values["conductivity"])
            q.append(values["flow"])
            diagnostics.append((values["conservation_inf"],values["backward_error"],values["scaled_rcond"]))
        if any(item != diagnostics[0] for item in diagnostics):
            raise ValueError("Inconsistent diagnostics within one state.")
        balance = [0.0]*4
        for edge,flow in zip(edges,q):
            balance[edge['from']] += flow
            balance[edge['to']] -= flow
        balance[int(config['source'])] -= config['current']
        balance[int(config['sink'])] += config['current']
        if max(abs(value) for value in balance) > 1e-12+1e-10*config['current']:
            raise ValueError("Recorded edge flows do not conserve the specified source-sink demand.")
        frames.append({"step":step,"time":time,"d":d,"q":q,"p":pressures,
                       "conservation":diagnostics[0][0],"backward_error":diagnostics[0][1],"rcond":diagnostics[0][2]})
    return RunData(config, edges, frames, files, origin)


def load_run(path):
    path = Path(path)
    if path.is_dir():
        files = {name:(path/name).read_bytes() for name in FILES if (path/name).is_file()}
    else:
        with zipfile.ZipFile(path) as archive:
            files = {name:archive.read(name) for name in FILES if name in archive.namelist()}
    return decode_run(files, str(path))


def save_run(data, path):
    path = Path(path)
    temporary = path.with_name(path.name+".tmp")
    try:
        with zipfile.ZipFile(temporary,"w",zipfile.ZIP_DEFLATED) as archive:
            for name, content in data.files.items():
                archive.writestr(name, content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run_experiment(executable, payload):
    config = validate_parameters(payload)
    with tempfile.TemporaryDirectory(prefix="physarum-viewer-") as temporary:
        folder = Path(temporary)
        path = folder/"input.cfg"
        path.write_text("".join(f"{key}={value}\n" for key,value in config.items() if key != "duration"))
        result = subprocess.run([str(executable),str(path),str(folder/"run")],capture_output=True,text=True,timeout=30)
        if result.returncode:
            raise ValueError(result.stderr.strip().removeprefix("Error: ") or "C++ experiment failed.")
        data = load_run(folder/"run")
        data.origin = "New C++ experiment (unsaved)"
        return data
