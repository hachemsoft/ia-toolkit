---
name: design
description: "Build: shape a module interface or answer a design question with a throwaway prototype"
category: workflow
stage: Build
skills: [codebase-design, prototype]
artifact: "interface sketch or prototype"
order: 80
---

Activate the codebase-design skill (if the skill tool is unavailable here, do not look for an agent of that name: follow the instructions below directly); activate the prototype skill when the question needs running code to be answered.

Input: {{args}}

Write the problem in one paragraph (responsibility, callers, constraints). For an interface question, produce two or three radically different designs, compare them on interface size, depth, seam placement, testability and cost of likely change, and recommend one. For a question that needs a runnable answer, build a throwaway prototype in a separate directory, answer the question, and say what it does not prove. Record a hard-to-reverse decision as an ADR via domain-modeling. Do not implement production code here; hand over to /build.
