# OpenCode 3-agent qwen workflow

This package is designed for the workflow:

```text
/work -> planner -> researcher if needed -> programmer using qwen3.5
```

It contains:

```text
opencode.json
AGENTS.md
.opencode/
  agents/
    planner.md
    researcher.md
    programmer.md
    debugger.md
    kubernetes.md
  commands/
    work.md
    code.md
    research.md
    plan.md
    debug.md
    kubernetes.md
```

## Install

From your project root:

```bash
cp -r opencode.json AGENTS.md .opencode /path/to/your/repo/
```

Or copy the files manually into the repo root.

Then start OpenCode from the repo root:

```bash
opencode
```

For web search with researcher, launch with Exa enabled if your OpenCode/provider needs it:

```bash
OPENCODE_ENABLE_EXA=1 opencode
```

## Model note

The programmer agent is set to:

```yaml
model: litellm/qwen3.5
```

If your local/OpenCode model ID is different, change this one line in:

```text
.opencode/agents/programmer.md
```

Examples you might need depending on your provider setup:

```yaml
model: openrouter/qwen/qwen3.5-coder
model: litellm/qwen3.5
model: ollama/qwen3.5-coder
```

Use `opencode models` to see exact model IDs available in your environment.

## Smoke tests

### 1. Agent discovery

```bash
opencode agent list
```

Expected agents:

```text
planner
researcher
programmer
debugger
kubernetes
```

### 2. Planner should not edit

In OpenCode:

```text
@planner Create PLANNER_SHOULD_NOT_WRITE.txt with content hello.
```

Expected: Planner refuses to edit or invokes Programmer. Planner should not ask for edit permission.

### 3. Full workflow

```text
/work Create WORKFLOW_OK.txt with content OK.
```

Expected:

```text
planner -> programmer child session -> file created -> planner summary
```

### 4. Direct programmer fallback

```text
/code Create WORKFLOW_OK_DIRECT.txt with content OK.
```

Expected: Programmer directly creates the file and reports verification.

### 5. Researcher test

```text
/research What is the current OpenCode syntax for custom commands?
```

Expected: Researcher uses web tools and does not inspect repo files.

### 6. Debugger test

```text
/debug Check if /app/runs exists in the bat3 worker pod
```

Expected: Debugger uses kubectl exec with ls and reports findings. No files are modified.

### 7. Kubernetes test

```text
/kubernetes Get pods --all-namespaces
```

Expected: Kubernetes agent uses kubectl get and reports pod list. No local files are modified.

## If the programmer appears frozen

OpenCode subagent work happens in child sessions. Navigate into the child session with the default child-session keybinding, commonly Leader + Down. If the child only listed files and stopped, use the direct fallback:

```text
/code [same implementation task]
```

The programmer prompt includes an anti-stall rule: it must edit, verify, or return `PROGRAMMER_BLOCKED`.
