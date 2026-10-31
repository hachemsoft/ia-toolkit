---
name: review
description: "Deploy: review the changes, committed or not, on bugs, security, standards and the spec when there is one"
category: workflow
stage: Deploy
skills: [code-review]
artifact: "review findings"
order: 50
---

Activate the code-review skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly) and follow it: it is the kit's single review behaviour, the same whether the person types /review or asks in a sentence.

Stage: Deploy. Goal: ranked findings a human can act on before merging.

Input: {{args}} (optional: a base ref such as main, "staged", "local", a path or a commit to narrow the scope, then "quick" or "full"; default: everything that changed since the default branch, committed or not, at a level inferred from the size and the paths touched, and stated).

Scope: the branch's commits since the base, the staged and unstaged changes and the new files, as the skill's scope commands list them; state the scope in one line; conclude "nothing to review" only when all of them are empty. Passes: Bugs, Security, Domain (the installed playbooks matching the files; delegate to the matching ai-kit-*-reviewer agent when available), Standards (REVIEW.md, AGENTS.md, the practices in your context), Compliance (spec.md, intent.md or plan.md when one exists; otherwise skipped, and said). Never ask for a spec or a ticket tracker to start. Severity: Important, Minor, Nit, as the skill defines them; at most five nits. In "full" mode, before concluding, list the claims the change relies on, doubt each one and look for proof or a counter-example (delegate to the ai-kit-doubter agent when available). Domain playbooks: when an installed playbook (listed in 00_KIT.md) matches the files or the task, follow it, including its "In the kit commands" section for this step. Do not fix anything; report only. Use the terms of GLOSSARY.md when it exists. Report format: if the repo's AGENTS.md or the user's 30_USER.md has a "## Report" section, shape the final report as it says (the repo's section wins over the user's); otherwise: the scope line, findings tagged with pass and severity, then the limits. Cross-area impact: when the repo has areas with their own AGENTS.md (a monorepo), name every other area reached by the changed files and what depends on them (as the matching domain playbook defines it), so the right owners review.
