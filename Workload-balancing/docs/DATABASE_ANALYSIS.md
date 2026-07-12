# Phase 1 — SyncVerse Database Analysis (Workload Analysis Feature)

Source: `SyncVerseDB` (SQL Server, EF Core / ASP.NET Identity backend), schema-only script, 28 tables.
This document is the single source of truth referenced by every later phase. **Read-only** — nothing here implies or requires a schema change.

---

## 1. Table-by-table purpose

### Identity / Auth (ASP.NET Core Identity — not workload-relevant, listed for completeness)
| Table | Purpose |
|---|---|
| `AspNetUsers` | The core **user/employee** record. Also carries domain fields EF Identity doesn't normally have: `SeniorityLevel` (int enum), `Department` (int enum), `Skills` (string, appears to hold a delimited/JSON list), `Gender`, `CurrentWorkspaceId`. This is our **Employee** entity. |
| `AspNetRoles`, `AspNetUserRoles`, `AspNetRoleClaims`, `AspNetUserClaims`, `AspNetUserLogins`, `AspNetUserTokens` | Standard Identity plumbing (login, claims, external providers). Irrelevant to workload analysis. |
| `__EFMigrationsHistory` | EF Core migration bookkeeping. Irrelevant. |

### Organizational structure
| Table | Purpose |
|---|---|
| `Workspaces` | Top-level tenant/organization container. Everything (`Teams`, `Projects`, `Tasks`, `Notifications`) hangs off a workspace. |
| `UserWorkspace` | Many-to-many: which users belong to which workspace. |
| `Teams` | A team within a workspace: `Specialization` (int enum), `Department` (int enum), `TeamLeaderId`, `CreatedByManagerId`. |
| `TeamMembers` | Many-to-many: user ↔ team, with `Role` (int enum) and `IsActive`. Optionally scoped to a `ProjectId`. |
| `CompanyInvitations`, `ProjectInvitations` | Onboarding workflow. Irrelevant to workload math, but `SeniorityLevel`/`Role` on `CompanyInvitations` hints at the same enums used on `AspNetUsers`. |

### Projects
| Table | Purpose |
|---|---|
| `Projects` | A project inside a workspace: `StartDate`, `EndDate`, `Budget`, `Status` (int enum), optional `TeamId`. |
| `ProjectMembers` | Many-to-many: user ↔ project, with **permission flags** (`CanAssignTasks`, `CanReviewTasks`, `CanEditProject`) and `Role`. Unique on `(ProjectId, UserId)`. |
| `Milestones` | Project checkpoints: `StartDate`, `EndDate`, `IsCompleted`. |
| `ProjectAttachments` | File attachments on a project. Not workload-relevant. |

### Tasks — the core of workload analysis
| Table | Purpose |
|---|---|
| `Tasks` | **The authoritative task table.** `Status` (int enum), `Priority` (int enum), `AssignedToUserId`, `CreatedByUserId`, `ReviewedByUserId`, `DueDate`, `CategoryId`, `ProjectId`, `MilestoneId`, `WorkspaceId`, plus a full submission/review lifecycle: `TaskStartedAt`, `SubmittedAt`, `TaskCompletedAt`, `ReviewedAt`, `ReviewComment`. This is the richest, most heavily-indexed table (indexed on `AssignedToUserId`, `ProjectId`, `MilestoneId`, `CategoryId`, `WorkspaceId`, `ReviewedByUserId`, `UserId`) — clear signal it's the live/primary task model. |
| `TaskEmployees` | A **secondary/legacy-looking** task table: its own `TaskTitle`, `Priority`, `Status`, `Deadline`, `ProgressPercentage`, `AssignedUserId`, `ProjectId`. It is *not* linked to `Tasks` by FK — it's an independent table, only connected in via `TimeLogs.TaskEmployeeId`. **Treated as a secondary/optional data source, not authoritative** (see §5). |
| `TaskDependencies` | Self-referencing: `TaskId` depends on `DependsOnTaskId`. Useful for context-switching / blocked-task inference. |
| `TaskCategories` | User-defined task categories/tags. |
| `TaskComments` | Threaded comments (`ParentCommentId` self-FK). Volume can be a soft signal of collaboration load. |
| `TaskAttachments` | File attachments on a task. Not workload-relevant. |

### Time tracking
| Table | Purpose |
|---|---|
| `TimeLogs` | Actual logged time per task per user: `StartTime`, `EndTime`, `DurationInMinutes`, `IsManual`, optional link to `TaskEmployeeId`. This is the **only source of real effort/capacity data** in the whole schema. |

### Misc
| Table | Purpose |
|---|---|
| `Notifications` | Not workload-relevant (except optionally as an activity-volume proxy). |
| `Meetings` | Vivox/meeting metadata with AI-generated `Summary`/`KeyPoints`/`Decisions`. Could be a future signal for "meeting load" but out of scope for v1. |
| `UserSettings` | `AvailabilityStatus` (free-text string!), `StatusMessage`, notification prefs. **Important**: `AvailabilityStatus` is a **string**, not a numeric score — see gap analysis below. |

---

## 2. Key relationships (FKs)

```
Workspaces 1─* Teams, Projects, Tasks, Notifications
Teams 1─* TeamMembers *─1 AspNetUsers
Projects 1─* ProjectMembers *─1 AspNetUsers
Projects 1─* Milestones 1─* Tasks
Tasks *─1 AspNetUsers (AssignedToUserId, CreatedByUserId, ReviewedByUserId, UserId)
Tasks *─1 TaskCategories
Tasks 1─* TaskComments, TaskAttachments
Tasks *─* Tasks (via TaskDependencies)
TaskEmployees *─1 AspNetUsers (AssignedUserId) — independent of Tasks
TimeLogs *─1 Tasks, *─1 AspNetUsers, *─0..1 TaskEmployees
```

**Employee identity for workload purposes = `AspNetUsers.Id`.** All workload metrics key off this.

---

## 3. Database → Workload Metric → AI-Estimated Metric mapping

| DB Table.Column(s) | Derived Workload Metric | Type |
|---|---|---|
| `Tasks` WHERE `AssignedToUserId = X AND Status NOT IN (Done, Cancelled)` | **Active Tasks** count | Deterministic |
| `Tasks` WHERE `AssignedToUserId = X AND Status = Assigned/InProgress` | **Assigned Tasks** count | Deterministic |
| `Tasks.DueDate < now() AND Status NOT IN (Done, Cancelled)` | **Delayed/Overdue Tasks** count | Deterministic |
| `Tasks.Priority` (per active task, aggregated) | **Priority Load** (sum/avg of numeric priority across active tasks) | Deterministic |
| `Tasks.TaskStartedAt`, `TaskCompletedAt`, `SubmittedAt`, `ReviewedAt` | **Cycle time**, **review turnaround time** | Deterministic |
| `TimeLogs.DurationInMinutes` grouped by `UserId` over a rolling window | **Time Consumption / Logged Hours** | Deterministic |
| `TimeLogs` hours vs. a configured capacity-per-day constant | **Capacity Utilization**, **Available Capacity**, **Remaining Capacity** | Deterministic |
| `Tasks` count per `AssignedToUserId` across the team | **Task Distribution**, **Team Utilization** (variance across team) | Deterministic |
| `Tasks.Status = Done AND ReviewComment/ReviewedAt present` vs. total | **Productivity Score** (completion rate, on-time rate) | Deterministic |
| `TaskDependencies` where the user's active tasks are blocked-on / blocking others | **Blocked Task Ratio** | Deterministic |
| `TaskComments` volume on tasks assigned to X | **Collaboration Volume** (raw count) | Deterministic |
| — *no numeric column exists* — | **Estimated Task Difficulty / Work Complexity** | **AI Estimated** (from `Task.Title` + `Description` + `TaskCategories.Name` + historical cycle-time-vs-similar-tasks) |
| — *no numeric column exists* — | **Burnout Indicator** | **AI Estimated** (from trend of active-task count, delayed-task ratio, logged-hours trend, `UserSettings.StatusMessage` free text if present) |
| — *no column exists* — | **Productivity Trend** (improving/declining) | **AI Estimated** (from week-over-week deterministic completion-rate series) |
| — *no column exists* — | **Focus Capacity** | **AI Estimated** (from active-task count × task-switching frequency + `TaskDependencies` blocking pattern) |
| — *no column exists* — | **Context Switching Cost** | **AI Estimated** (from number of distinct `ProjectId`/`CategoryId` a user is concurrently active on) |
| — *no column exists* — | **Collaboration Difficulty** | **AI Estimated** (from `TaskComments` sentiment/volume + review rejection rate) |
| — *no column exists* — | **Estimated Priority Weight** | **AI Estimated** (reconciles `Tasks.Priority` enum with task title/description urgency language) |
| `AspNetUsers.Skills` (free-text/delimited string) | Skill-task match quality (used in redistribution) | **AI Estimated** (parsed + matched against task title/category; the raw string itself is deterministic to *read*, but "match quality" requires semantic judgment) |
| `UserSettings.AvailabilityStatus` (free string, e.g. "Busy", "Away") | Numeric **Availability Score (0–100)** | **AI Estimated** — this is the clearest schema gap: the old in-memory model expected a 0–100 `availability_score` float; the real DB only has a free-text status. AI enrichment converts status text + deterministic active-task/capacity numbers into a normalized score. |

## 4. Deterministic vs. AI classification (summary)

**Deterministic (pure Python, no LLM call):**
Active Tasks, Assigned Tasks, Delayed Tasks, Priority Load, Cycle Time, Logged Hours, Capacity Utilization, Available/Remaining Capacity, Task Distribution, Team Utilization, Productivity Score (completion rate), Blocked Task Ratio, Comment Volume, task-complexity-distribution *counts* (once complexity itself is known).

**AI Estimated (LLM, batched into one call per employee-set):**
Estimated Task Difficulty, Estimated Work Complexity, Burnout Indicator, Productivity Trend (qualitative judgment on the deterministic series), Focus Capacity, Context Switching Cost, Collaboration Difficulty, Estimated Priority Weight, Availability Score normalization, Skill-match quality.

This exactly matches the constraint in your spec: **the AI only estimates what cannot be derived mathematically** from the available columns.

## 5. Missing information & how it's inferred (no schema changes)

| Gap | Why it's missing | AI inference strategy |
|---|---|---|
| No numeric `AvailabilityScore` | `UserSettings.AvailabilityStatus` is free text, not a score | LLM enrichment maps status text + deterministic load numbers → 0–100 score with `confidence` |
| No `TaskComplexityDistribution` (low/med/high/critical) | `Tasks` has no complexity/story-point field, only `Priority` | LLM classifies each active task into a complexity bucket from `Title`+`Description`+`TaskCategories.Name`; counts are then aggregated deterministically |
| No burnout / sentiment signal | Not tracked anywhere structured | LLM enrichment reasons over the deterministic trend series (rising delayed-tasks, rising logged-hours, falling completion rate) |
| Two task tables (`Tasks` vs `TaskEmployees`) with unclear precedence | Likely legacy migration artifact — `TaskEmployees` predates or parallels `Tasks` | Production `BackendDataProvider` reads from `Tasks` as authoritative; `TaskEmployees` is read only as a fallback if `Tasks` returns nothing for a workspace (configurable, logged as a data-quality warning — **not silently merged**) |
| `AspNetUsers.Skills` format unknown (CSV? JSON? free text?) | Column is `nvarchar(max)`, no CHECK constraint | Provider layer parses defensively (JSON first, then comma-split fallback); AI enrichment only judges *match quality*, never the raw parse |

## 6. What this means for the architecture

- The old in-memory `Employee`/`Task` Pydantic models (`active_tasks`, `availability_score`, `task_complexity_distribution` as **direct request-body input**) map almost 1:1 to the **Context Builder's internal `WorkloadContext`** — but now that context is *populated*, not *supplied by the caller*. The public API surface changes from "push me your numbers" to "give me a project/team/workspace id" (Production) or "give me a scenario name" (Demo).
- The existing `WorkloadMonitor → RiskAnalyzer → RedistributionEngine` pipeline is preserved **unchanged** as the deterministic core (§ Metrics Engine + Workload Engine in the new architecture) — it already expects exactly this shape of `Employee`/`Task` objects, so the Context Builder's job is simply to *produce* them from real or demo data instead of trusting the caller.

Next: architecture validation + scaffolding (Data Provider Layer, Context Builder, AI Enrichment, LLM Provider Layer), implemented directly against this mapping.
