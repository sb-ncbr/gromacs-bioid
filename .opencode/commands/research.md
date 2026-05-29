---
description: Direct web/current-info research fallback. Runs researcher as a subtask.
agent: researcher
subtask: true
---

Research this question.

Question:
$ARGUMENTS

Rules:
- Use websearch/webfetch only.
- Do not inspect local files.
- Prefer official/current sources.
- Return a compact implementation-oriented research brief.
