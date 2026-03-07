# research-project — SPEC

## Background

A one-shot research project template. Replace this with your actual research topic.

## Iron Rules

- Knowledge docs in Chinese (通俗易懂), code in English
- Each task produces exactly ONE output file
- Tasks must be self-contained
- Keep each output file under 50KB

## Goals

1. Survey existing tools and approaches
2. Analyze feasibility and trade-offs
3. Design a prototype architecture
4. Estimate costs and timelines

## Phase 0: Knowledge Building

| ID  | Title               | Depends On | Output                       |
|-----|---------------------|------------|------------------------------|
| 0.1 | Technology survey   | —          | `knowledge/tech-survey.md`   |
| 0.2 | Competitor analysis | —          | `knowledge/competitors.md`   |
| 0.G | Gate: Phase 0 done  | 0.1, 0.2   | —                            |

Gate conditions: All knowledge/ files exist and are non-empty.

## Phase 1: Analysis & Design

| ID  | Title               | Depends On | Output                       |
|-----|---------------------|------------|------------------------------|
| 1.1 | Architecture design | 0.G        | `output/architecture.md`     |
| 1.2 | Cost estimation     | 0.G        | `output/cost-model.md`       |
| 1.G | Gate: Phase 1 done  | 1.1, 1.2   | —                            |

Gate conditions: All output/ files exist and each >= 1KB.

## Phase 2: Report

| ID  | Title               | Depends On | Output                       |
|-----|---------------------|------------|------------------------------|
| 2.1 | Final report        | 1.G        | `output/final-report.md`     |
| 2.G | Gate: Complete      | 2.1        | —                            |

Gate conditions: output/final-report.md exists and >= 2KB.

## Output Structure

```
knowledge/
├── tech-survey.md
└── competitors.md
output/
├── architecture.md
├── cost-model.md
└── final-report.md
```
