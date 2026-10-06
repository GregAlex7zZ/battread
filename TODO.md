# Future work

## Reader compatibility

- [ ] Obtain redistributable matching MPR/MPT exports covering accessory fields
  and additional recording conventions. Add independent numerical regressions.
- [ ] Validate complete real Neware NDA/NDAX acquisitions and matching exports.
  Binary support remains experimental; CSV autoexports are the current focus.
- [ ] Investigate rejected Neware framing, conflicting split-file checkpoints
  and distinctions between padding and final measurements. Preserve explicit
  failure until semantics are verified.
- [ ] Expand Neware CSV profiles while preserving Total Time precedence.

## Performance

- [ ] Benchmark wider, multi-GB and NaN-heavy inputs, including reconstruction;
  measure peak committed memory, physical RAM, disk use and throughput.
- [ ] Benchmark two independent conversion processes against sequential work.
  Introduce parallel scheduling only with bounded queues, a shared memory budget,
  unique outputs and equivalent scientific results. Preserve chunk boundary state.
- [ ] Evaluate a PyArrow CSV fast path only after dialect, units, malformed cells,
  warning behavior and scientific equivalence are demonstrated.
- [ ] Profile capacity reconstruction before optimizing its stateful processing.

## Maintenance

- [ ] Validate macOS and ARM before claiming tested support.
- [ ] Recheck dependency upgrades against supported Python versions, minimum
  requirements, licensed fixtures and exact distribution artifacts.
- [ ] Add a regression for every real parsing/recognition issue.
- [ ] Keep examples runnable and notebook outputs cleared before committing.
- [ ] Review English documentation, third-party notices and limitations each release.

Cycle, capacity and energy analysis and plotting remain outside library scope.
