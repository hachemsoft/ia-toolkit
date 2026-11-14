# Can a small classifier model decide what the agent may run?

Question asked during the 4.8.0 redesign of `protected-paths`: instead of rules on the text of a command, could a
non-autoregressive decision model judge whether a shell command run by an agent changes the configuration of the kit or of
a CLI? Measured once, offline, outside the kit. Nothing of it ships.

## What was measured

- **Model**: Laya, the base English checkpoint [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya)
  (ModernBERT-large encoder, about 421 M parameters, Apache 2.0), run on a laptop CPU with torch 2.15.0 and transformers
  5.23.0. Model files 820 MB, private environment 965 MB, loading 24.5 s.
- **Use**: one two-option question with neutral keys (A: it changes such a file; B: it only reads it or writes elsewhere),
  as the model card advises for the English checkpoint without fine-tuning; a decision threshold fitted on 10 labelled
  commands kept out of the evaluation.
- **Data**: 191 shell commands labelled by one annotator (109 change a configuration file, 82 do not), taken from the
  guardrail tests and from commands seen in real sessions; 181 evaluated.
- **Baseline**: the `protected-paths` hook of 4.7.1 on the same commands, with an empty home folder.

| | Laya, threshold | Hook 4.7.1 | Closed list of obvious writes (not shipped) |
| --- | --- | --- | --- |
| Changes caught | 81 / 104 | 101 / 104 | 97 / 109 |
| False alarms on reads | 36 / 77 (47 %) | 7 / 77 (9 %) | 0 / 82 |
| Median time per command | 186 ms (plus loading) | 19 ms | 19 ms |
| Same answer on two runs | yes | yes | yes |

The last column, a rule tried during the 4.8.0 redesign and then dropped (reviews found holes in it per shell and system),
is measured on all 191 commands. 4.8.0 reads no shell command and checks the installed files after each tool call instead
([ADR 0030](../adr/0030-check-the-result-not-the-command.md)).

## What it says

The base model reacts to the presence of a sensitive path, not to what the command does with it: it flagged
`cat ~/.ai-kit/aikit.toml` and let `cp new.toml ~/.ai-kit/aikit.toml` through.

## What it does not say

This is **not** a fair test of what Laya can do. Its card states that the base checkpoints are near chance on decisions
without fine-tuning (0.362 on its own benchmark, 0.766 once fine-tuned on that benchmark) and presents Laya as a base to
specialise. A fair test would fine-tune it on a few thousand labelled commands (the publisher's notebook runs on two
free cloud GPUs, so the commands would leave the machine), fit its calibration temperatures, and evaluate on held-out
commands. Only one question wording and one annotator were used.

## Why it was not pursued

Even a well fine-tuned model keeps what the kit rules out: a model of close to 1 GB and its runtime on every workstation
(ADR 0003, no model in the kit; ADR 0004, no network at install), some 190 ms before every command the agent runs, and
errors that are probabilistic, so no test can prove that a given write is always refused. What it could add is what the
integrity check already reports after each tool call, exactly and at a small cost per call. Worth reopening only if
the kit ever accepts a model at run time.
