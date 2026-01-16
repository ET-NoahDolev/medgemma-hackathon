# Getting Started

## Prerequisites

- Python 3.12
- UV package manager
- Node.js 18+ (for HITL UI)
- Docker (optional, for local DB)

## Setup

```bash
uv sync
make docs-build
```

To run the HITL UI (after scaffolding):

```bash
cd components/hitl-ui
npm install
npm run dev
```
