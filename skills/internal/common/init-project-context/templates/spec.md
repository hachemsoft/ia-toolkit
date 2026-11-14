# Spec: <title> (from intent.md <date>)

Status: draft | accepted · Reviewed by: <product owner> · Date: <YYYY-MM-DD> · Versioned: this file is the contract reviewers read in the merge request (MR)

## Objective
<One sentence tied to the intent's Proposed outcome.>

## Scope and non-goals
- In: <…>
- Out: <…>

## Requirements
Each requirement has a verifiable acceptance criterion.
1. <Requirement> — Acceptance: <what you observe when it is done>.

## Contracts
<What the change exposes or relies on, for others: an API, an event, a table, a file. Delete this section if it touches none.>
| Object | Shape (fields, or one row per … for data) | Key | Sources | Freshness | Rules (compatibility, dates, exclusions, NULL) |
| --- | --- | --- | --- | --- | --- |
| <endpoint, event, model or table> | <…> | <…> | <…> | <…> | <…> |

## Constraints and policies applied
<Company, team and domain practices applied while writing, with the rule cited.>

## Threats
<Only when the change touches personal data, secrets or tokens, authentication or permissions, input from outside or an external service; delete this section otherwise. One line per threat: threat — mitigation — residual risk. The review checks each mitigation.>

## Areas of concern
<Where two rules contradict each other, where a requirement cannot be met, where cost or risk is significant. Each point names who decides.>

## Open questions
- <…>
- Assumption: <what this spec takes as true without proof, and how to check it.>
