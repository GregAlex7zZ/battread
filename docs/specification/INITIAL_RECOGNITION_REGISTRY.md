# Initial Recognition Registry
## Version 0.1

**Status:** Initial implementation baseline  
**Related specification:** Column Recognition Specification v0.1

---

# 1. Purpose

This document defines the initial vocabulary and semantic rules that shall seed the column-recognition registry.

It is not intended to be exhaustive.

The registry is expected to grow continuously through:

- real-world files;
- regression tests;
- user reports;
- vendor-specific knowledge;
- contributions from the electrochemistry community.

The initial implementation shall prioritize correctness over vocabulary size.

---

# 2. General registry principles

Aliases shall be divided into:

```text
generic aliases
vendor-specific aliases
negative terms
unit aliases
semantic capacity aliases
```

Ordinary aliases should be stored declaratively.

Recognition behavior shall not depend on source-column order.

Single-letter symbols require stronger supporting evidence than descriptive names.

Vendor-specific knowledge may override generic uncertainty when the source format is known.

---

# 3. Time — generic aliases

## 3.1 Strong descriptive aliases

Initial aliases should include normalized variants of:

```text
time
elapsed time
elapsed
test time
total time
experiment time
measurement time
run time
runtime
time elapsed
total elapsed time
```

Unit-bearing forms shall be recognized automatically:

```text
time/s
time (s)
time [s]
elapsed time/s
elapsed time (s)
test time (s)
```

## 3.2 Symbol alias

```text
t
```

shall be treated as weak-to-moderate evidence unless combined with a compatible time unit.

For example:

```text
t/s
t (s)
```

is substantially stronger than bare:

```text
t
```

## 3.3 Negative / non-canonical time terms

The following concepts must not normally be selected as total elapsed time:

```text
step time
cycle time
half cycle time
half-cycle time
segment time
phase time
pulse time
rest time
charge time
charging time
discharge time
discharging time
```

## 3.4 Absolute time candidates

The following may represent absolute timestamps:

```text
timestamp
date time
datetime
date/time
absolute time
date
```

They are fallback time candidates when elapsed time is unavailable.

An explicit elapsed-time column should normally outrank an absolute timestamp.

---

# 4. Current — generic aliases

## 4.1 Strong descriptive aliases

Initial aliases should include:

```text
current
cell current
measured current
measurement current
current measured
cellcurrent
```

`Applied Current` may mean measured current or a commanded value. It MUST NOT resolve automatically as generic measured current, even with compatible units. Verified vendor semantics or explicit user mapping is required.

## 4.2 Scientific-symbol aliases

```text
I
Icell
I cell
```

shall be supported.

Bare `I` is weaker than:

```text
I/mA
I/A
I (mA)
I [A]
```

because the compatible unit strongly supports the interpretation.

## 4.3 Unit-bearing examples

The recognizer should successfully identify variations such as:

```text
Current(mA)
Current (mA)
Current [mA]
Current/mA
Current / mA
I/mA
I/A
I (A)
Cell Current (mA)
```

## 4.4 Strong negative terms

A current candidate shall receive strong negative evidence when its label contains concepts such as:

```text
range
limit
upper limit
lower limit
maximum
minimum
max
min
setpoint
set point
target
programmed
control
compliance
density
specific
threshold
cutoff
cut-off
```

Examples that must not normally resolve as canonical current:

```text
Current Range
Current Limit
Current Setpoint
Target Current
Programmed Current
Current Density
Specific Current
Maximum Current
Minimum Current
```

## 4.5 Derived current quantities

The following unit families shall exclude a column from canonical absolute-current recognition:

```text
A/g
mA/g
A/kg
mA/cm2
mA/cm²
A/m2
A/m²
```

unless future functionality explicitly introduces the required conversion information.

---

# 5. Voltage — generic aliases

## 5.1 Strong descriptive aliases

Initial aliases should include:

```text
voltage
cell voltage
measured voltage
measurement voltage
potential
cell potential
measured potential
```

## 5.2 Scientific symbols

Potential symbols may include:

```text
V
E
U
```

These are weak when isolated and stronger when paired with voltage units or vendor-specific knowledge.

Examples:

```text
E/V
U/V
Voltage/V
```

## 5.3 Strong negative terms

Negative terms should include:

```text
limit
upper limit
lower limit
maximum
minimum
max
min
setpoint
set point
target
programmed
control
range
cutoff
cut-off
compliance
threshold
```

Examples not normally selected:

```text
Voltage Limit
Upper Voltage
Lower Voltage
Voltage Setpoint
Target Voltage
Programmed Voltage
Cutoff Voltage
Voltage Range
```

## 5.4 Multiple measured potentials

The following shall remain potentially ambiguous in generic files:

```text
Cell Voltage
Reference Voltage
Working Electrode Voltage
Counter Electrode Voltage
```

No generic priority rule shall silently choose between scientifically distinct measured potentials.

Vendor knowledge or explicit user selection is required where necessary.

---

# 6. Capacity — generic aliases

Capacity recognition shall be divided between identifying the quantity and identifying its semantics.

---

# 7. Generic capacity candidates

The following may indicate capacity without defining its semantic subtype:

```text
capacity
cap
Q
capacity passed
charge passed
total capacity
```

Without stronger evidence these shall resolve only as:

```text
generic_capacity
```

and shall not automatically trigger current reconstruction.

---

# 8. Charge-capacity aliases

Strong charge-capacity aliases should include normalized variants of:

```text
charge capacity
charging capacity
chg capacity
chg cap
charge cap
Q charge
Qcharge
capacity charge
charge Q
```

Compatible absolute capacity units strengthen recognition.

---

# 9. Discharge-capacity aliases

Strong discharge-capacity aliases should include:

```text
discharge capacity
discharging capacity
dchg capacity
dchg cap
discharge cap
Q discharge
Qdischarge
capacity discharge
discharge Q
```

---

# 10. Incremental / delta capacity aliases

Possible incremental-capacity aliases include:

```text
dq
dQ
delta q
delta Q
delta capacity
capacity increment
incremental charge
charge increment
```

However, labels such as `dq` shall only acquire strong reconstruction semantics when vendor-specific knowledge or other reliable context establishes how the value is aligned with time.

The registry must not supply a generic default alignment. A `delta_signed` field requires authoritative reader semantics or an explicit `capacity_interval="previous"` or `capacity_interval="next"` declaration. Previous-aligned values refer to the preceding adjacent source interval; next-aligned values refer to the following adjacent source interval.

---

# 11. Capacity exclusions

The following shall be treated as derived quantities rather than usable absolute capacity:

```text
specific capacity
gravimetric capacity
areal capacity
volumetric capacity
capacity density
```

Likewise capacity units containing normalization factors shall be excluded from automatic current reconstruction:

```text
mAh/g
Ah/kg
mAh/cm2
mAh/cm²
Ah/L
C/g
```

---

# 12. Unit registry — time

Canonical target:

```text
s
```

Initial recognized aliases:

```text
s
sec
secs
second
seconds

ms
msec
msecs
millisecond
milliseconds

us
µs
μs
microsecond
microseconds

min
mins
minute
minutes

h
hr
hrs
hour
hours

d
day
days
```

Conversion factors to seconds shall be explicit and tested.

Across all unit registries, SI symbol and prefix case must be preserved. Quantity-label case folding must not accept unsupported `MA` as `mA`, or `Ms` as `ms`. Unit aliases may normalize only spellings explicitly registered as equivalent.

---

# 13. Unit registry — current

Canonical target:

```text
mA
```

Initial aliases:

```text
A
amp
amps
ampere
amperes

mA
mamp
mamps
milliamp
milliamps
milliampere
milliamperes

uA
µA
μA
microamp
microamps
microampere
microamperes

nA
nanoamp
nanoamps
nanoampere
nanoamperes
```

---

# 14. Unit registry — voltage

Canonical target:

```text
V
```

Initial aliases:

```text
V
volt
volts

mV
millivolt
millivolts

uV
µV
μV
microvolt
microvolts
```

---

# 15. Unit registry — capacity

Reference internal reconstruction unit:

```text
mAh
```

Initial aliases:

```text
Ah
A.h
A h
ampere hour
ampere-hour

mAh
mA.h
mA h
milliampere hour
milliampere-hour

uAh
µAh
μAh

C
coulomb
coulombs
```

Conversions shall include:

```text
1 Ah  = 1000 mAh
1 C   = 1 / 3.6 mAh
1 mAh = 3.6 C
```

---

# 16. Bio-Logic initial overlay

The Bio-Logic adapter shall provide authoritative semantics for fields known through its parser whenever possible.

Initial known examples include:

```text
time/s       → time, s
Ewe/V        → voltage, V
I/mA         → current, mA
dq/mA.h      → capacity-related quantity, mAh
```

The precise semantics of `dq/mA.h` shall be determined by the Bio-Logic adapter and tested against representative files before being used automatically for current reconstruction.

These semantics must include signedness and previous/next interval alignment. A recognized capacity unit does not establish them. Independently known resets must cause reconstruction to fail in v0.1; vendor overlays must not enable reset unwrapping.

Additional Bio-Logic fields shall be added through regression fixtures rather than guessed from names alone.

---

# 17. Neware initial overlay

The Neware adapter shall prefer semantic information produced by its parsing backend where available.

Because exported field names may vary across Neware hardware/software generations, the implementation shall not assume a single universal textual schema.

Vendor-specific aliases shall be populated from:

- actual parsed NDA/NDAX fixtures;
- documented backend outputs;
- regression tests.

Generic recognition shall remain available as fallback.

---

# 18. Canonical aliases

The following names are authoritative canonical columns:

```text
time_s
current_mA
voltage_V
```

When all three exist unambiguously, generic alias scoring should be bypassed.

---

# 19. Initial negative-term registry

A central negative-term registry should initially contain terms such as:

```text
limit
range
setpoint
set point
target
programmed
control
maximum
minimum
upper
lower
threshold
cutoff
cut-off
compliance
density
specific
nominal
command
requested
```

Negative terms may have quantity-specific meanings.

They shall not necessarily be applied identically to every physical quantity.

---

# 20. Registry contribution rule

Every added alias or negative rule MUST be accompanied by at least one test.

A bug fix involving false recognition SHOULD include both:

```text
positive fixture/test
negative regression test
```

where relevant.

---

# 21. Initial implementation principle

This registry is deliberately conservative.

The first release should recognize a smaller number of headers correctly rather than a much larger number unreliably.

Expansion shall be driven by real data.
