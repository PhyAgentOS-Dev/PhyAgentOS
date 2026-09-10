---
name: robodojo
description: Run the RoboDojo G05 benchmark and report its aggregate score.
metadata: {"PhyAgentOS":{"always":false,"requires":{"runtime":["robodojo"]}}}
---

# RoboDojo Benchmark

Run a RoboDojo benchmark batch in Isaac Sim and report the score the benchmark
produced. Use only these stable Tool IDs:

- `bench.describe`: Query; return the live task inventory, defaults, and episode
  budget limits. Does not touch the simulator state.
- `bench.run`: Action; run one batch of episodes and return its aggregate result.
  Long running — minutes per episode.

Use the PAOS bridge tools `forge_tool_context`, `forge_tool_query`,
`forge_tool_start_action`, `forge_tool_action_status`, `forge_tool_action_result`,
and `forge_tool_cancel_action`. Always pass the stable Forge Tool ID explicitly.
Do not use shell commands and do not construct Gateway HTTP requests directly.

## What this Skill must not do

Scoring belongs entirely to the benchmark node. This Skill selects and sequences
Tools, and reports what came back. It must not:

- compute, recompute, adjust, average, or extrapolate `success_rate` or any other
  metric;
- decide whether an individual episode succeeded, failed, or timed out;
- aggregate results across separate `bench.run` invocations into one number;
- convert a partial or failed batch into a score, or present one as if the batch
  had completed;
- estimate a score when the result is unavailable.

If a number is needed and no terminal result exists, say so. Do not produce one.

## 1. Always describe before running

Call `bench.describe` first, every time. Never fill `bench.run` arguments from
memory or from an earlier conversation — the installed suite, task count, and
limits are properties of the running profile, not of this document.

`bench.describe` returns:

- `benchmark`, `suite`, `policy_id`, `env_cfg_type`, `action_type` — fixed by the
  profile. They are read-only context, not parameters you can change.
- `tasks[]` — each with `task_id`, `name`, `language`, `num_init_states`. The
  init-state count differs per task; do not assume one task's count applies to
  another.
- `defaults` — `num_runs`, `seed`, `max_steps` to use when the user gave no value.
- `limits` — `max_total_episodes`, `max_max_steps`. Hard caps; see §2.

If `bench.describe` fails with `BENCH_NOT_READY`, the simulator is still starting.
Wait and retry; do not proceed to `bench.run`.

## 2. Build the bench.run arguments

All five fields are required. There are no defaults on the wire.

- `task_ids`: an array of ids taken from `bench.describe`, or `null` for every
  task. `null` and `[]` are different — `[]` is always an error, never "all".
- `init_state_ids`: an array, or `null` for every init state shared by all
  selected tasks. Validated per task.
- `num_runs`: repeats per (task, init_state) pair. Use `defaults.num_runs` unless
  the user asked for more.
- `seed`: base seed. The same seed and the same ids reproduce the same episodes.
  Change it only when the user asks for a different sample.
- `max_steps`: a **hard cap on control steps**. The episode is terminated as
  `timed_out` if this many steps are reached before the environment ends. The
  task native `step_lim` defines its normal end (success / partial / failed); set `max_steps` to at least the task horizon (from `bench.describe` defaults) to allow completion, or lower to force an explicit step-limit stop.

Episode count is `len(task_ids) x len(init_state_ids) x num_runs`. Keep it at or
below `limits.max_total_episodes`; exceeding it is rejected, not clamped. When the
user asks for something larger, report the cap and the requested count and ask
before splitting the work into several batches.

Nothing else is selectable. Policy weights, suite, camera set, and GPU are fixed by
the profile. If the user asks to change one of those, say it requires a different
profile — do not try to express it through these arguments.

## 3. Account for the Action lifecycle

`bench.run` is an Action. Accepted is not completed.

1. `forge_tool_start_action` returns an acknowledgement with an `invocation_id` and
   `total_episodes`. The batch has not run yet.
2. `forge_tool_action_status` reports `accepted`, `running`, or a terminal phase.
   Status is **advisory** — never report a score from it. Poll at a human pace;
   a single episode takes minutes.
3. `forge_tool_action_result` is the only authoritative source of the outcome.

Treat the four terminal outcomes as four different things:

- `succeeded` — the batch ran to completion. Report per §4.
- `failed` — the batch ended abnormally. Report the error code and the episode
  counts; do not present `success_rate` as the headline.
- `cancelled` — stopped on request. Partial counts only.
- `unknown` — **the outcome cannot be recovered**. Side effects have already
  happened: GPU time was consumed and a `result.json` may exist on disk. Do not
  blindly retry. Report that the outcome is unknown, give the `invocation_id`, and
  ask how to proceed.

Use `forge_tool_cancel_action` only when the user asks to stop. Cancel is accepted,
not immediate — keep polling until a terminal result appears.

## 4. Reporting rules

Report these together, always, in this order:

1. `status` of the batch.
2. `success_rate`, immediately followed by `successes` / `total_episodes`.
3. `completed_episodes` / `total_episodes`.

`success_rate` is computed over `total_episodes`, not over
`completed_episodes`. When a batch ends early these differ, and `success_rate`
alone reads as "the policy scored low" when the real story is "the batch did not
finish". If `completed_episodes < total_episodes`, say that first, before the
score.

Also report:

- `result_path` — the authoritative record on disk. Always include it.
- `timed_out_episodes` when non-zero.
- `obs_republished` when non-zero: observations were re-sent during the run. The
  score is still valid, but mention it.
- `episodes[]` per-episode outcomes when the user asks for detail. When
  `episodes_truncated` is true the list was too large to inline — point at
  `result_path` instead of summarising from an empty array.

Never present a single number without its denominator.

## 5. Errors and replanning

| code | retryable | what to do |
|---|---|---|
| `BENCH_NOT_READY` | yes | Simulator still starting. Wait, retry `bench.describe`. |
| `FORGE_BUSY` | yes | Another batch is running; one simulator per machine. Report which `invocation_id` holds it. Do not queue. |
| `BENCH_INVALID_ARGUMENT` | no | Arguments are wrong. Re-read `bench.describe` and rebuild them. `details` carries the valid range and the requested vs allowed episode count. Never retry unchanged. |
| `BENCH_NODE_UNAVAILABLE` | yes | The benchmark node stopped reporting. The outcome is unknown — see §3. Do not restart the batch without asking. |
| `BENCH_UNKNOWN_INVOCATION` | no | The id is not known here. Do not invent one; start a new run if the user wants one. |
| `FORGE_DEADLINE_EXCEEDED` | no | The gateway stopped tracking; the batch may still be running. Do not start another — that would collide. Report and ask. |

When two errors are plausible, prefer the more conservative reading: an unknown
outcome is not a failure, and a rejected batch is not a zero score.
