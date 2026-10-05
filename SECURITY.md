# Security

Input files are untrusted data. Readers validate recognized framing and table
structure, but this version does not impose file-size, archive-expansion or
execution-time limits. Use process and resource limits when processing files
from untrusted sources. Scientific correctness failures also merit regression
tests and clear release notes.

## Reporting

Use GitHub's **Report a vulnerability** form on the repository's Security tab:
https://github.com/GregAlex7zZ/battread/security/advisories/new.
The maintainer must enable private vulnerability reporting before this channel
is advertised as operational. Its activation is a publication checklist item;
the URL alone does not establish that the GitHub setting is enabled.

If the private form is unavailable, an ordinary GitHub issue may request that
the channel be enabled, without vulnerability details. Do not post credentials,
private acquisitions, exploit instructions or sensitive reports publicly.
Ordinary nonsensitive parsing bugs can use GitHub Issues with a synthetic or
redistributable reproducer.

## Version policy

Security reports are considered for the latest published release only. Older
versions are not maintained separately. Version 0.1.0 is prepared but has not
been published yet. No response time, security certification, support or fix
commitment is promised; the GPL warranty and liability provisions apply.
