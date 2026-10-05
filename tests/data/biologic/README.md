# Bio-Logic regression data

The unchanged `020-formation_CB5.mpr` and `020-formation_CB5.mpt` acquisition
comes from [Galvani's test data](https://github.com/echemdata/galvani/tree/d4a5f444b16eae57d2edfad6df774ead95c92fd6/tests/testdata).
The binary file and BT-Lab ASCII export describe the same 1,323 source rows.

Copyright: **Chihyu Chen <chihyu.chen@molicel.com>**.
License: **CC-BY-4.0**, as recorded in the adjacent unchanged `.license` files.
The [Creative Commons Attribution 4.0 terms](https://creativecommons.org/licenses/by/4.0/legalcode.en)
apply to these two acquisition files. They retain their original names and
content; this attribution does not imply endorsement of battread.
The unchanged official license text is included as [CC-BY-4.0.txt](CC-BY-4.0.txt).

SHA-256:

- MPR: `586836288e1144454c277ecd6adfc384bfe1614ed141900c5f004b26a8b54d64`
- MPT: `c323f95a3f5f1465d07ef8654a86df1de65e3a5dc3af11e7fb27d187f2ffe43e`

The test reference uses Python's standard CSV parser on the **BT-Lab export**,
selecting `time/s`, `I/mA`, and `Ecell/V`; it does not derive expected values
from Galvani. Binary comparisons allow `rtol=1e-7`, `atol=1e-7` for ASCII
rounding of single-precision instrument values. The tested backend is
**Galvani 0.5.0**.

Capacity tests derive a reduced MPT at runtime from the exported time, voltage,
charge-capacity, and discharge-capacity columns. The first 588 rows form a
reset-free prefix; including row 588 (zero-based) introduces a known decrease
in charge capacity and must fail. Expected interval current is calculated
independently from the exported values with the specified difference formula.
This selection is a test recipe, never an automatic truncation by the reader.

Dq tests remove the measured-current column and retain the exported `dq/mA.h`.
Expected interval current is calculated independently from the original dq
and preceding timestamps. MPT derivatives retain both cumulative capacities,
including their resets, to verify dq preference. Binary derivatives encode
the same exported time, voltage, and dq in an independently constructed MPR
wire layout. These derivatives are synthetic, based on the attributed export;
the unchanged original files remain the direct-current acceptance references.

Additional small binary fixtures are constructed at runtime using `struct`
and explicitly declared column IDs and wire types. They test binary-schema
handling, duplicate fields, and pair reconstruction against hand-computed
values. They are labelled synthetic and do not claim instrument provenance.
