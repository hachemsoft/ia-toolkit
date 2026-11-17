---
name: me
description: "Fill or refresh your personal context (USER.md) through a short interview: your domains, how you want answers, how to work with you"
category: tool
skills: []
order: 105
---

Input: {{args}} (optional: what to change, for example "simpler answers in reviews").

Goal: a USER.md that changes how you answer this person, at most 20 lines. Interview them; never guess.

Where it is: ~/.ai-kit/context/USER.md. Read it first: it is theirs; keep what they wrote unless they change it.

1. Facts first, never asked, only these: the current file, git config user.name, OS and shell, CLIs on the PATH, the repo's languages, the team in the kit context. Say in two lines what you found and how many questions remain.

2. Ask, as simply as possible. Every question:
   - is short (twelve words at most), in everyday words, in their language: never "autonomy", "verbosity" or "persona";
   - offers two or three options, each a label of a few words and a concrete example after a dash; your recommendation first, marked "(recommended)";
   - comes in batches of at most four, through your CLI's question tool when it has one, otherwise as a numbered list.
   Read ~/.ai-kit/me/questions.md and ask its questions in its order. Skip a question when the current file or the input already answers it; if the input names one change, ask only about that. If that file is missing, say so: the kit needs `ai-kit sync`.

3. Write the proposal in the sections of the file: Me, Domains, Answers, Working with me, By situation, Report. Each line: an instruction to you, in English, imperative, that changes something observable; nothing you would do anyway or that 00_KIT.md or 10_CORE.md already covers; no opinion about tools or technologies (only form and context: stored opinions make an assistant agree too easily); keep the two lines under the title and the line "When my idea is risky or wrong, say so plainly with the evidence before acting. My preferences are about form, never about conclusions." whatever they chose. At most 20 lines of instructions, the most important first. Never put a secret, a token or someone else's personal data in it. Then replay three situations against it (a review, a small fix, a disagreement): if two lines answer one differently, ask which one wins.

4. Show the difference with the current file (lines added, changed, removed), then a before and after: answer one real question of theirs (or one they give) as you would without the file, then with it, a few lines each. Wait for their go-ahead; change what they ask.

5. With their agreement only, write the file (plain UTF-8, same place). Then say: start a new session of the CLI to load it; in Gemini CLI and Codex CLI, run ai-kit sync --offline first (they read a copy). Offer three first prompts suited to their role.

Never edit 00_KIT.md, 10_CORE.md, a 20_<TEAM>.md or the kit's settings: if they want a rule for everyone, say it goes through the kit repository.
