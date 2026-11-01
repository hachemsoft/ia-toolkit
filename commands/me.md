---
name: me
description: "Fill or refresh your personal context (30_USER.md) through a short interview: your domains, how you want answers, how to work with you"
category: tool
skills: []
order: 105
---

Input: {{args}} (optional: what to change, for example "simpler answers in reviews").

Goal: a 30_USER.md that changes how you answer this person, at most 20 lines. Interview them; never guess.

Where it is: ~/.ai-kit/context/30_USER.md (before 0.39: ~/.gemini/30_USER.md). Read it first: it is theirs; keep what they wrote unless they change it.

1. Facts first, never asked: read the current file, git config user.name, the operating system and shell, the repo's languages, the profile and team in the kit context. Say in two lines what you found and how many questions remain.

2. Ask, as simply as possible. Every question:
   - is short (twelve words at most), in everyday words, in their language: never "autonomy", "verbosity" or "persona";
   - offers two or three options, each a label of a few words and a concrete example after a dash; your recommendation first, marked "(recommended)";
   - comes in batches of at most four, through your CLI's question tool when it has one, otherwise as a numbered list.
   Skip a question when the current file or the input already answers it; if the input names one change, ask only about that. Use these questions, worded this simply, in this order:
   1. "What is your job, and what are you working on these weeks?" (one line, free text)
   2. For each domain you found: "<domain>: how much do you know?" A. A lot — skip the basics. B. Some — explain the choices. C. Little — explain step by step. Then: "A topic you love to dig into, even as a beginner?" (free text, for example C4 diagrams)
   3. "Which answer do you prefer?" Show the same short answer to one of their real questions twice: A in three lines, B with the why and an alternative.
   4. "When my task is clear, I…" A. Do it, then tell you (recommended). B. Tell you, then do it. C. Wait for your go-ahead.
   5. "If I think your idea is wrong, I…" A. Say so, with my reasons (recommended). B. Ask you a question. C. Suggest another way.
   6. "Another tone somewhere?" A. No. B. Reviews simpler, more teaching — one point at a time. C. Other — say where.
   7. "What annoys you in an assistant?" (several allowed) A. Too long. B. Rewrites whole files. C. Makes things up — commands, options. D. Asks too much.
   8. "Languages?" A. Answers in <their language>, code and commits in English (recommended). B. Everything in <their language>.
   9. "Anything I cannot guess?" (optional, free text: no admin rights, a tool you must use, a network constraint)
   Ask about the end-of-run reports of /build, /test, /diagnose and /review only if they bring it up (a "## Report" section).

3. Write the proposal in the sections of the file: Me, Domains, Answers, Working with me, By situation, Report. Each line: an instruction to you, in English, imperative, that changes something observable; nothing you would do anyway; no opinion about tools or technologies (only form and context: stored opinions make an assistant agree too easily); keep the two lines under the title and the line "When my idea is risky or wrong, say so plainly with the evidence before acting. My preferences are about form, never about conclusions." whatever they chose. At most 20 lines of instructions, the most important first. Never put a secret, a token or someone else's personal data in it.

4. Show the difference with the current file (lines added, changed, removed), then a before and after: answer one real question of theirs (or one they give) as you would without the file, then with it, a few lines each. Wait for their go-ahead; change what they ask.

5. With their agreement only, write the file (plain UTF-8 text, same name and place). Then say: start a new session of the CLI to load it; in Gemini CLI and Codex CLI, run update first (they read a copy). Offer three first prompts suited to their role.

Never edit 00_KIT.md, 10_COMPANY.md, 20_TEAM.md or the kit's settings: if they want a rule for everyone, say it goes through the kit repository.
