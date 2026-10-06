# MPR reader architecture

The Bio-Logic adapter owns bounded ingestion while Galvani 0.5.x remains an
optional source of known column definitions, packed flags, module headers and
date parsing. Keeping it avoids an unnecessary rewrite of established format
knowledge. No backend objects escape the adapter and no installed package or
global schema map is patched.

## Bounded ingestion

Scan module headers while seeking over payloads. Normalize NumPy uint32 header
values to Python integers before advancing the backend iterator so large-file
seek arithmetic cannot wrap. Validate container bounds, required/duplicate
modules, reserved bytes, record counts and auxiliary metadata before reading
scientific values. Supported data layouts are version 0 (legacy and paired-ID
encodings), 2 and 3, with both supported module header formats.

Read structured record arrays with explicit positive counts and an 8 MiB binary
buffer ceiling. This avoids full-source bytes and mappings that retain resident
pages. Wide tables reduce effective canonical chunk size to limit intermediate
string rows. Open sources lazily, close iterators on completion/cancellation and
reject detected source changes. `read()` still collects a complete result;
`iter_read()` and `convert()` are the bounded-consumption interfaces.

## Verified accessory fields

The adapter skips these noncanonical fields as opaque bytes, using explicit
[yadg registry definitions](https://github.com/dgbowl/yadg/blob/main/src/yadg/extractors/eclab/mpr_columns.py)
checked on 2026-10-06:

| ID | Description | Bytes |
|---|---|---|
| 115 | Counter-electrode charge energy | 8 |
| 116 | Counter-electrode discharge energy | 8 |
| 175 | Zwe-ce impedance magnitude | 4 |
| 176 | Zwe-ce real impedance | 4 |
| 177 | Zwe-ce negative imaginary impedance | 4 |
| 182 | Step time | 8 |
| 215 | Average counter-electrode voltage | 4 |

Credit to Nicolas Vetsch, Peter Kraus and collaborators. No yadg code or package
is bundled. These are specific upstream format facts, not a vendor-published
specification or a general unknown-field fallback. Unknown widths are never
guessed from plausible values or total payload size.

Backend prefix sizes locate skips without duplicating packed flag bytes or
renaming known fields. Preserve mixed widths and duplicate names; verify the
complete payload size against declared records. Exclude opaque fields from
recognition and numeric conversion. Step time must not replace experiment time,
and counter-electrode voltage must not become working-electrode voltage.

## Scientific boundaries and evidence

Measured-current precedence/sign, verified dq reconstruction, missing rows,
zero-origin time and backward-time errors remain unchanged. Multiple candidate
voltages still require explicit column selection; the library does not assume
`Ewe/V` and `<Ewe>/V` are interchangeable.

Independent synthetic wire fixtures cover layouts, field positions, mixed skips,
flags, malformed bounds, source changes, cancellation and chunk equivalence.
Licensed MPR/MPT references cover numerical interpretation. The synthetic
[memory benchmark](benchmarks.md) measures ingestion, separately from complete
normalization. Additional redistributable matching exports remain useful
coverage; no claim of universal instrument/version compatibility is made.
