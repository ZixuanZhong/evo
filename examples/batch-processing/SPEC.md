# batch-processing — SPEC

## Background

示例：批量处理项目。展示 `auto_split` 功能 — 当上游任务产出的工作量在 plan 阶段未知时，
worker 在运行时自动将任务拆分为多个子任务，避免超时。

## Goals

1. 扫描目标目录，生成待处理文件清单
2. 批量处理所有文件（自动拆分，每批不超时）
3. 汇总处理结果

## Phase 0: 扫描
| ID  | Title             | Depends On | Output              |
|-----|-------------------|------------|---------------------|
| 0.1 | 扫描待处理文件     | —          | `output/file-list.txt` |

## Phase 1: 批量处理（auto_split）
| ID  | Title             | Depends On | Output              |
|-----|-------------------|------------|---------------------|
| 1.1 | 处理所有文件       | 0.1        | `output/processed.md` |

> **注意**: 任务 1.1 使用 `auto_split`，worker 运行时会根据 `output/file-list.txt`
> 的行数自动拆分为 `1.1.1`, `1.1.2`, ... 子任务，原任务变为 gate。

## Phase 2: 汇总
| ID  | Title             | Depends On | Output              |
|-----|-------------------|------------|---------------------|
| 2.1 | 汇总处理结果       | 1.1        | `output/summary.md` |
| 2.G | Gate: 完成         | 2.1        | —                   |
