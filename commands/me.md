---
name: me
description: "Fill or refresh your personal context (30_USER.md) through a short interview: your domains, how you want answers, how to work with you"
category: tool
skills: []
order: 105
---

Input: {{args}} (optional: what to change, for example "simpler answers in reviews").

Goal: a 30_USER.md that changes how you answer this person, in at most 20 lines. Interview them; never write it from guesses.

Where it is: 30_USER.md in ~/.gemini/ if that file exists, otherwise in ~/.ai-kit/context/. Read it first: it belongs to the person, the kit never rewrites it, and you keep what they wrote unless they change it.

1. Facts first, never asked: read what you can see (the current file, git config user.name, the operating system and shell, the languages and tools of the repo you are in, the profile and team named in the kit context). Say in two lines what you found and how many questions remain.

2. Two rounds of questions, numbered, each with options A, B, C and your recommendation, so that "yes" accepts it. For the closed questions, use your CLI's question tool when it has one (the person picks instead of typing), with your recommendation as the first option; otherwise list the options in text. Skip a question when the current file or the input already answers it; if the input names one change, ask only about that change. Ask:
   - Their role and what they are working on these weeks, in one sentence.
   - Their domains, from what you found: for each, how deep to go (expert: skip basics; familiar; new: explain the choices) and whether it is a passion they want to go deeper into, separately from their level (someone can be new to C4 diagrams and love them).
   - Answer format, by example: write the same short answer to one of their real questions in two forms (a short one, and a detailed one with the why) and let them pick.
   - Autonomy when the request is clear: A do it and say what you did, B say what you will do then do it, C ask first.
   - When their idea is risky or wrong: A say so plainly with the evidence before acting (recommended), B ask a question, C propose an alternative.
   - By situation, only if they want a different tone somewhere: reviews, diagnosis, explanations, architecture (for example "reviews: simpler and more teaching, one finding at a time").
   - What annoys them in an assistant (open question; offer examples: too long, rewrites whole files, invents APIs or flags, asks too much, too little).
   - Languages: of the answers, of code and comments, of commit messages.
   - What you cannot guess: tools imposed, rights (no admin), network constraints.
   - Optional: how they want the end-of-run reports of /build, /test, /diagnose and /review (a "## Report" section).

3. Write the proposal in the sections of the file: Me, Domains, Answers, Working with me, By situation, Report. Rules for every line: an instruction to you, in English, in the imperative; it changes something observable in an answer; nothing you would do anyway; no opinion about tools or technologies (only form and context: stored opinions make an assistant agree too easily); keep the two lines under the title and the line "When my idea is risky or wrong, say so plainly with the evidence before acting. My preferences are about form, never about conclusions." whatever they chose. At most 20 lines of instructions, the most important first. Never put a secret, a token or someone else's personal data in it.

4. Show the difference with the current file (lines added, changed, removed), then a before and after: answer one real question of theirs (or one they give) as you would without the file, then with it, a few lines each. Wait for their go-ahead; change what they ask.

5. With their agreement only, write the file (plain UTF-8 text, same name and place). Then say: start a new session of the CLI to load it; in Codex CLI, run update first (Codex keeps a copy of it). Offer three first prompts suited to their role.

Never edit 00_KIT.md, 10_COMPANY.md, 20_TEAM.md or the kit's settings: if they want a rule for everyone, say it goes through the kit repository.
