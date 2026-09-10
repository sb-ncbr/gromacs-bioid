# Function-Based Context Structure

## Core Concept
Organize context files by function, not by topic hierarchy. Each folder serves a distinct purpose in the verification workflow.

## Key Points
- **concepts/**: What things are (definitions, mental models)
- **examples/**: How things look (concrete command/output samples)
- **guides/**: How to do things (step-by-step procedures)
- **lookup/**: Quick reference (commands, status tables, codes)
- **errors/**: What goes wrong (symptoms, causes, fixes)

## Folder Layout

```
.opencode/context/
├── core/context-system/     # Meta-standards for context itself
│   ├── standards/           # MVI rules, structure definitions
│   └── guides/              # How to maintain context
└── bat3/                    # Project-specific context
    ├── concepts/            # What BAT3 is, validation pipeline
    ├── examples/            # Sample commands and outputs
    ├── guides/              # Running validation, indexing
    ├── lookup/              # Commands, status numbers
    └── errors/              # Common issues and fixes
```

## Reference
- `mvi.md` - File size and content standards
