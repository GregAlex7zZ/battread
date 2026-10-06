# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Verify the public notebook stays output-free, synthetic and executable.

The notebook exercises the installed public API without real acquisitions,
Jupyter-specific execution dependencies or persisted output. This prevents the
introductory instructions from drifting away from actual scientific behavior.
"""

import json
from pathlib import Path
from typing import cast

import pandas as pd


def test_getting_started_notebook_runs_through_public_workflow() -> None:
    """Run every code cell and check unit conversion, merge order and canonical data."""
    path = Path(__file__).resolve().parents[1] / "examples/getting_started.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "__notebook_example__"}
    try:
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                assert cell["outputs"] == []
                assert cell["execution_count"] is None
                exec(
                    compile("".join(cell["source"]), f"example-cell-{index}", "exec"),
                    namespace,
                )
        data = cast(pd.DataFrame, namespace["data"])
        assert list(data.columns) == ["time_s", "current_mA", "voltage_V"]
        assert all(str(dtype) == "float64" for dtype in data.dtypes)
        assert data.time_s.tolist() == [0.0, 1.0, 3.0]
        assert data.current_mA.tolist() == [-2.0, 3.0, -4.0]
        pd.testing.assert_frame_equal(data, cast(pd.DataFrame, namespace["round_trip"]))
        assert namespace["rows_processed"] == 3
        combined = cast(pd.DataFrame, namespace["combined"])
        assert combined.time_s.tolist() == [0.0, 1.0, 3.0, 5.0, 6.0]
        custom = cast(pd.DataFrame, namespace["custom_data"])
        assert custom.time_s.tolist() == [0.0, 60.0]
        assert custom.current_mA.tolist() == [-2.0, 3.0]
        assert custom.voltage_V.tolist() == [3.5, 3.6]
        assert not cast(Path, namespace["folder"]).exists()
    finally:
        workspace = namespace.get("workspace")
        cleanup = getattr(workspace, "cleanup", None)
        if cleanup is not None:
            cleanup()
