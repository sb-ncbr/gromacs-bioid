---
description: Read-only planning only. No implementation unless explicitly asked to proceed.
agent: planner
---

Analyze this request and produce a concise implementation plan only.

Request:
$ARGUMENTS

Rules:
- Read repo files as needed.
- Ask blocking questions if needed.
- Do not edit.
- Do not run bash.
- Do not invoke programmer unless the user explicitly asks you to proceed.
