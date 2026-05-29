---
description: Direct qwen3.5 implementation fallback. Runs programmer as a subtask.
agent: programmer
subtask: true
---

Execute this implementation task directly.

Task:
$ARGUMENTS

Rules:
- Make the smallest correct change.
- Do not browse.
- Do not ask the human questions.
- Do not stop after listing files.
- Edit, verify, and report changed files.
