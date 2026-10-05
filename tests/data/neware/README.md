# Neware fixtures

Source: https://github.com/d-cogswell/NewareNDA at commit
`d895eb23eb7e1514b32f2dc7fcf8e856822fd197`. BSD-3-Clause, see LICENSE.

- `small.ndax`: `tests/nda/github/Issue27_2/ZZZZZZZZTEST.ndax`.
- `conflicting.ndax`: `tests/nda/github/Issue94/123456789012_Unit27_Example_Data_File.ndax`.
  Two checkpoints associate different timestamps with index 1; rejected.
- `prefix.nda`: first 112475 bytes of
  `tests/nda/neware_reader/new_nda_file.nda`, ending before unknown AA framing.
  This derived prefix exercises complete version-29 measurement records.

The tested backend is NewareNDA 2026.6.11. All canonical voltage and current
values in the real fixtures are independently decoded from wire fields. NDA
calendar timestamps are independently converted to elapsed seconds. NDAX
checkpoint indices, seconds and milliseconds are decoded independently and
checked against every finite/missing output time. The NDA reference has range
code 5 (current integer times 0.0001 mA); split NDC16 stores voltage in 0.0001 V
and current in mA. No backend generates expected tables. Float comparisons
allow 1e-12 relative/1e-14 absolute tolerance for decimal parsing roundoff.

Synthetic wire fixtures are constructed with standard struct packing for
NDA130 BTS9/BTS9.1, full NDC2/NDC5 and split NDC11/NDC14/NDC16/NDC17. Their
hand-declared reference is time [0,2,4] seconds and current [2.5,-1.25,0] mA;
voltage is 3.5 V, with an interior zero-voltage sample in split layouts. They
verify sign, units, step-clock independence, padding and chunk equivalence.
Split layouts storing A are encoded with current divided by 1000. The 1e-7
relative tolerance reflects float32 wire precision. These fixtures are
synthetic compatibility checks, not additional instrument acquisitions.
Manufacturer-export comparisons and more real hardware variants remain desirable.

SHA-256:

- `prefix.nda`: `9ed581f802a01e84ddce435d7b099e975c71e41f4fe6f3857a644d94c30c5f72`
- `small.ndax`: `c980080b0477f4f99a21023cb04e88bc1a17f880719ea80f06f53d51053594ee`
- `conflicting.ndax`: `9f7198e5f3854bcb91b8bad268f020836ed1aa48f0135e2f7b1515827e61c9f6`
