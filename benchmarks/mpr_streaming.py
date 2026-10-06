# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fresh-process MPR ingestion memory comparison using synthetic files only.

Run with --output benchmarks/mpr-memory.json. This measures binary ingestion
separately from the shared scientific pipeline, and labels that scope explicitly.
No throughput requirement or private acquisition information is recorded.
"""

import argparse
import ctypes
import json
import os
import platform
import struct
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np

from battread.readers.biologic import _load_mpr

# The benchmark deliberately exercises the adapter's isolated schema boundary.
# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false


def peak_memory() -> dict[str, int]:
    """Return OS lifetime resident/committed peaks, including native allocations."""
    if os.name != "nt":
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {"rss_bytes": int(rss if sys.platform == "darwin" else rss * 1024)}

    class Counters(ctypes.Structure):
        """Represent PROCESS_MEMORY_COUNTERS fields needed for both Windows peaks."""

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
    return {
        "rss_bytes": int(counters.PeakWorkingSetSize),
        "committed_bytes": int(counters.PeakPagefileUsage),
    }


def synthetic(path: Path, payload_mib: int) -> None:
    """Write repeated known records in bounded buffers, independently of Galvani."""
    record = struct.pack("<dff", 0.0, -2.0, 3.5)
    rows = payload_mib * 1024**2 // len(record)
    header = struct.pack("<IBHHH", rows, 3, 4, 8, 6).ljust(405, b"\x00")
    with path.open("wb") as stream:
        stream.write(b"BIO-LOGIC MODULAR FILE\x1a".ljust(48) + b"\x00" * 4)
        for name, module_version, length in (
            (b"VMP Set   ", 0, 0),
            (b"VMP data  ", 2, len(header) + rows * len(record)),
        ):
            stream.write(b"MODULE")
            stream.write(
                struct.pack(
                    "<10s25sII8s", name, name, length, module_version, b"01/01/24"
                )
            )
        stream.write(header)
        block = record * 65_536
        while rows:
            count = min(rows, 65_536)
            stream.write(block[: count * len(record)])
            rows -= count


def worker(case: str, source: Path, chunk: int) -> dict[str, Any]:
    """Measure one isolated ingestion case, verifying every encoded current value."""
    from galvani import BioLogic  # pyright: ignore[reportMissingImports]

    baseline = peak_memory()
    started = time.perf_counter()
    if case == "legacy":
        with source.open("rb") as stream:
            parsed = BioLogic.MPRfile(stream)
        rows = len(parsed.data)
        assert np.all(parsed.data["I/mA"] == -2.0)
    else:
        rows = 0
        for array in _load_mpr(source).iter_arrays(chunk):
            assert np.all(array["I/mA"] == -2.0)
            rows += len(array)
            del array
    return {
        "case": case,
        "synthetic_file_bytes": source.stat().st_size,
        "rows": rows,
        "chunk_rows": chunk,
        "elapsed_s": time.perf_counter() - started,
        "baseline": baseline,
        "peak": peak_memory(),
    }


def main() -> None:
    """Generate synthetic inputs and record isolated worker memory measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes-mib", nargs="+", type=int, default=[32, 128])
    parser.add_argument("--chunk", type=int, default=50_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/mpr-memory.json")
    )
    parser.add_argument("--worker", choices=("legacy", "streaming"))
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.source, args.chunk)))
        return
    results: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="battread-synthetic-mpr-") as temporary:
        for size in args.sizes_mib:
            source = Path(temporary) / f"synthetic-{size}.mpr"
            synthetic(source, size)
            for case in ("legacy", "streaming"):
                for _ in range(args.repeat):
                    result = subprocess.run(
                        [
                            sys.executable,
                            __file__,
                            "--worker",
                            case,
                            "--source",
                            str(source),
                            "--chunk",
                            str(args.chunk),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    results.append(json.loads(result.stdout))
    args.output.write_text(
        json.dumps(
            {
                "scope": "synthetic binary ingestion only; not full standardization",
                "platform": platform.system(),
                "python": platform.python_version(),
                "numpy": version("numpy"),
                "galvani": version("galvani"),
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(results)} synthetic memory measurements.")


if __name__ == "__main__":
    main()
