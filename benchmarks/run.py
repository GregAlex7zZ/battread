# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fresh-process timing and OS peak resident-memory baselines; no speed targets."""

import argparse
import ctypes
import json
import platform
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pyarrow.csv as arrow_csv

from battread import convert, iter_read, merge, read, write
from battread.normalization.time import normalize_time
from battread.recognition import recognize_columns


def peak_rss() -> int:
    """OS lifetime peak, including native Arrow/numpy memory and imports."""
    if sys.platform != "win32":
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value * 1024)

    class Counters(ctypes.Structure):
        """Map Windows process memory counters to obtain native peak resident memory."""

        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Counters),
        ctypes.c_ulong,
    ]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PeakWorkingSetSize)


def frame(rows: int) -> pd.DataFrame:
    """Generate reproducible canonical float64 data of the requested row count."""
    return pd.DataFrame(
        {
            "time_s": np.arange(rows, dtype=np.float64),
            "current_mA": np.full(rows, -2.0),
            "voltage_V": np.full(rows, 3.5),
        }
    )


def worker(case: str, rows: int, chunk: int, directory: Path) -> dict[str, object]:
    """Measure one case in a fresh process and return timing and OS memory data.

    The parent invokes this through --worker so earlier benchmark allocations
    do not contaminate the process lifetime peak. Setup occurs outside timing
    where the case permits it; native allocations are included in peak RSS.
    """
    source = directory / f"generic-{rows}.csv"
    prepared = (
        frame(rows) if case in {"merge", "parquet_write", "normalization"} else None
    )
    baseline = peak_rss()
    started = time.perf_counter()
    observed = rows
    if case == "read":
        observed = len(read(source))
    elif case == "arrow_csv_probe":
        # Parsing-only investigation, without the library's scientific validation.
        reader = arrow_csv.open_csv(
            source, read_options=arrow_csv.ReadOptions(block_size=chunk * 32)
        )
        observed = sum(batch.num_rows for batch in reader)
    elif case == "iter_read":
        observed = sum(len(part) for part in iter_read(source, chunk_size=chunk))
    elif case == "canonical_iter":
        observed = sum(
            len(part)
            for part in iter_read(directory / f"canonical-{rows}.csv", chunk_size=chunk)
        )
    elif case == "parquet_iter":
        observed = sum(
            len(part)
            for part in iter_read(
                directory / f"canonical-{rows}.parquet", chunk_size=chunk
            )
        )
    elif case == "convert":
        convert(source, directory / "output.parquet", chunk_size=chunk, overwrite=True)
    elif case == "reconstruction":
        observed = sum(
            len(part)
            for part in iter_read(
                directory / f"capacity-{rows}.csv",
                chunk_size=chunk,
                columns={"capacity": "Capacity(mAh)"},
                capacity_kind="cumulative_signed",
            )
        )
    elif case == "recognition":
        for _ in range(rows):
            recognize_columns(("time/s", "Current(mA)", "Voltage(V)", "Capacity(mAh)"))
    elif case == "normalization":
        assert prepared is not None
        normalize_time(prepared.time_s.to_numpy())
    elif case == "parquet_write":
        assert prepared is not None
        write(prepared, directory / "output.parquet", overwrite=True)
    elif case == "merge":
        assert prepared is not None
        observed = len(merge([prepared, prepared]))
        assert observed == 2 * rows
    else:
        raise ValueError(case)
    elapsed = time.perf_counter() - started
    peak = peak_rss()
    assert observed == (2 * rows if case == "merge" else rows)
    return {
        "case": case,
        "rows": rows,
        "chunk_size": chunk,
        "seconds": elapsed,
        "rows_per_second": observed / elapsed,
        "peak_rss_bytes": peak,
        "pre_operation_peak_rss_bytes": baseline,
    }


def generate(directory: Path, sizes: list[int]) -> None:
    """Write reproducible input fixtures before timing begins.

    Use a temporary directory and a list of row counts. Canonical, generic and
    capacity inputs let cases compare parsing, I/O and reconstruction costs.
    """
    for rows in sizes:
        canonical = frame(rows)
        canonical.to_csv(directory / f"canonical-{rows}.csv", index=False)
        write(canonical, directory / f"canonical-{rows}.parquet")
        generic = canonical.rename(
            columns={
                "time_s": "time/s",
                "current_mA": "Current(mA)",
                "voltage_V": "Voltage(V)",
            }
        )
        generic.to_csv(directory / f"generic-{rows}.csv", index=False)
        capacity = generic.drop(columns="Current(mA)")
        capacity["Capacity(mAh)"] = -np.arange(rows, dtype=np.float64) / 1800
        capacity.to_csv(directory / f"capacity-{rows}.csv", index=False)


def main() -> None:
    """Run isolated benchmark cases and write measurements with environment metadata.

    Invoke python benchmarks/run.py --sizes 100000 --repeat 3. The --worker
    mode is an internal subprocess entry point. Results establish observed
    baselines; they do not impose an unsupported throughput target.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100_000, 1_000_000])
    parser.add_argument("--chunks", type=int, nargs="+", default=[10_000, 100_000])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.json"))
    parser.add_argument("--worker")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if args.worker:
        print(
            json.dumps(
                worker(args.worker, args.sizes[0], args.chunks[0], args.directory)
            )
        )
        return
    measurements = []
    with TemporaryDirectory(prefix="battread-benchmark-") as temporary:
        directory = Path(temporary)
        generate(directory, args.sizes)
        cases = []
        for rows in args.sizes:
            cases.extend(
                (case, rows, args.chunks[0])
                for case in (
                    "read",
                    "normalization",
                    "merge",
                    "parquet_write",
                )
            )
            cases.extend(
                (case, rows, chunk)
                for chunk in args.chunks
                for case in (
                    "iter_read",
                    "canonical_iter",
                    "parquet_iter",
                    "convert",
                    "reconstruction",
                )
            )
        cases.append(("recognition", 10_000, args.chunks[0]))
        if args.cases:
            requested = set(args.cases)
            cases = [case for case in cases if case[0] in requested]
            if "arrow_csv_probe" in requested:
                cases.extend(
                    ("arrow_csv_probe", rows, chunk)
                    for rows in args.sizes
                    for chunk in args.chunks
                )
            if not cases:
                parser.error("No matching benchmark cases")
        for case, rows, chunk in cases:
            for repetition in range(args.repeat):
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    case,
                    "--sizes",
                    str(rows),
                    "--chunks",
                    str(chunk),
                    "--directory",
                    str(directory),
                ]
                result = subprocess.run(
                    command, capture_output=True, text=True, check=True
                )
                measurement = json.loads(result.stdout)
                measurement["repetition"] = repetition
                measurements.append(measurement)
                print(case, rows, chunk, round(measurement["seconds"], 3), flush=True)
    payload = {
        "environment": {
            "platform": platform.platform(),
            "python": sys.version,
            "dependencies": {p: version(p) for p in ("numpy", "pandas", "pyarrow")},
        },
        "measurements": measurements,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
