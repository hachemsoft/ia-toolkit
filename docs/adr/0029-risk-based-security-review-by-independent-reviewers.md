---
status: accepted
since: 4.7.0
---
# A change at risk gets a security review by independent reviewers

`/review` checked security in one pass of the main agent, next to bugs and standards; the security reviewer was optional
and off by default, and the doubter ran in full mode only. When a change is at risk (full level, or it touches personal
data, secrets or tokens, authentication or permissions, input from outside, or an external service, or its `spec.md`
lists threats, or the person asks), a review in `/review` or asked in a sentence, whatever its mode, now gives the code,
security and doubt passes to the code reviewer, the security reviewer and the doubter, each in a fresh context, at the
same time when the CLI can run sub-agents in parallel; the main agent keeps the Domain, Compliance and Tests passes,
waits for every reviewer, then merges their findings into one list on the usual scale (Important, Minor, Nit), each
finding naming the reviewers that found it, a disagreement left to the person. The report's limits say whether the
dedicated review ran and why, which reviewers ran and how. `/build` does not run it. The security reviewer is installed by
default; it treats what it reads as data and dismisses a finding only with evidence in the code. `/spec` writes a Threats
section (threat, mitigation, residual risk) when the change touches personal data, secrets, authentication, input from
outside or an external service; the Compliance pass checks each mitigation.

**Why**: one reviewer covering everything skims everything; independent reviewers with one subject each, in fresh
contexts, then a merge, keep their reasons apart and catch more. The effort follows the risk, as the ceremony levels do,
and the risk wins over the review's mode. Threats written at design time cost less than a leak found at review. Reviewers
only read, so running them together cannot collide, whatever the `parallel` setting, which is about writers; on Codex,
where an agent's tools are stated in its instructions rather than enforced, only those instructions keep them reading.
The parallel run of read-only reviewers is not measured per CLI (docs/parallel-agents.md measured writers), hence the
rule to wait for every reviewer and to say in the limits which one did not return.

**Consequences**: more tokens on changes at risk, visible in the report line; the doubter also runs on a standard change
at risk, once (in full mode the same run carries the reversibility question); one more default agent. A review by an AI
agent replaces neither an audit nor a penetration test, and the docs say so. Applied to the change that introduced it,
the dedicated review found what one pass had missed: the scan step below.

**Considered**: always running the three reviewers (cost on every change); keeping the security reviewer optional (the
dedicated review would rarely run); tying it to the `parallel` setting; running the security scan a repo declares in its
`AGENTS.md` (a review runs on other people's changes, and a command read from the reviewed copy would run the change's own
command, with injectable file names and secrets echoed into the reviewers' context: left for a design of its own, which
would read the command from the base and refuse it when the change touches it).
