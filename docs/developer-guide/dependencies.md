# Dependency policy

Runtime requirements use tested minimum versions and avoid upper bounds unless
an upstream parser contract requires one. This keeps supported Python versions
resolvable while allowing compatible bug-fix and feature releases.
Documentation tooling retains MkDocs 1.x compatibility with the tested theme
and plugins; a major-version upgrade requires its own compatibility review.

The core consists of NumPy, pandas, and PyArrow. Galvani and NewareNDA are
optional and must only be imported within their reader adapters. Full audit
evidence and release-time obligations are tracked in the root
`THIRD_PARTY_NOTICES.md` file.

Minimum-version and current-version CI must pass before a release. Parser
behavior still needs representative, independently verified vendor fixtures;
successful installation or import does not establish scientific correctness.
