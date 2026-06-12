---
description: Safe remote Kubernetes debugging. Runs debugger as a subtask for read-only pod inspection.
agent: debugger
subtask: true
---

Debug this remote run or pod.

Request:
$ARGUMENTS

Rules:
- Only read-only commands (ls, cat, find, head, tail, grep, kubectl get/describe/logs/exec with safe commands).
- Never modify, write, or delete files in remote pods.
- Report only what is observed.
