---
name: report-check
description: "Check a report before it is published: filters, period, totals, labels. Triggers: check this report, before publishing the dashboard."
metadata:
  aikit-version: "1.0.0"
  aikit-origin: "team"
  aikit-summary: "Check a report before it is published: filters, period, totals, labels."
  aikit-category: "domain"
---

# report-check

1. Read the report's filters and period; say which ones the person did not choose.
2. Recompute one total from its source query; show both numbers.
3. Check each label against the team's glossary.

## In the kit commands

- `/review`: run these checks on a changed report before the code review.

## Forbidden

- Publishing or sharing the report.
- A total validated on a sample.
