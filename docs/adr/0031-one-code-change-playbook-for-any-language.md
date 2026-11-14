---
status: accepted
since: 4.9.0
---
# One code-change playbook for any language, language pitfalls in references

Two language playbooks, `python-js-change` and `java-change`, said mostly the same thing, and the first held nothing
specific to Python or JavaScript. They are replaced by one optional playbook, `code-change`, for a change to application
code in any language: the repo's conventions and two neighbouring files, public contracts, no new library and no implicit
framework migration, secrets out of code, test-first through the tdd skill, the repo's verification commands. What a
language adds goes to `references/<language>.md`, read only for a change in that language, and holds, short: the community
standard, the tools that enforce it when the repo already declares them, and classic traps. Python, JavaScript and
TypeScript, Java (the former `java-change`), PHP, Go and Scala. A convention of one repo goes to that repo's `AGENTS.md`.

**Why**: official skill guidance and the widely used public skill collections split skills by task or process, not by
language, and keep stack detail in reference files loaded on condition. Published measurements (2025-2026) find that
generic instructions the model already follows add little or nothing, that a skill's description competes in a listing
the CLIs cap (a share of the context window), and that skills with overlapping descriptions get confused with each other
more than their number hurts. One playbook with one description avoids two near-duplicates; references keep what is
specific without loading it for other languages. The sources are in the research note kept outside the public repository
(it names other skill collections).

**Consequences**: a person or Team that listed `python-js-change` or `java-change` in `extra_skills` lists `code-change`
instead; the old names are unknown to the kit (no alias: no installation depends on them). The PHP, Go and Scala references
are not measured: they are kept to concrete pitfalls, and one that does not prevent a mistake is to be cut.

**Considered**: one playbook per language (near-duplicate bodies, more descriptions in a capped listing, triggers that
collide); keeping `python-js-change` under its name (a misleading name for a language-agnostic body); folding the body into
`/build` and `tdd` (`/build` is at its size budget, and the playbook stays optional).
