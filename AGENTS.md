# Instructions for future code changes

Follow the source-of-truth specifications and implementation handoff. All
publishable code, documentation, examples and messages must be in English.
Never include private user inputs, derived outputs, source identifiers or
data-specific results in publishable files. Use synthetic examples or fixtures
with independently documented redistribution permission. Keep private working
files outside the repository and check final build artifacts before publication.

Document every Python module, class and function, including private helpers,
nested callbacks, tests and benchmark tools. Explain its purpose, how to use it
and why it is needed. An overload declaration shares the implementation's
docstring; do not duplicate documentation on overload stubs.

For public APIs, document arguments, return values or yielded values, expected
errors, warnings and a concrete example. Explain units, missing-value behavior,
side effects and memory constraints where relevant. For stateful helpers,
explain call order, lifetime, chunk-boundary state and finalization.

Use nearby comments to explain scientific or architectural reasoning that is
not evident from the code. Do not merely narrate syntax. Keep descriptions
accurate when behavior changes; avoid placeholders and unexplained magic values.
Tests must explain the invariant they protect; fixtures must explain the inputs
they construct. Documentation quality requires review, not just a passing check.

Read [the code guide](docs/developer-guide/code-guide.md) and
[CONTRIBUTING.md](CONTRIBUTING.md). Before finishing changes, run the documentation
presence check, relevant tests, Ruff lint/format checks and Pyright. Build the
documentation when changing docstrings or Markdown. Do not alter scientific
behavior solely to simplify its explanation.
