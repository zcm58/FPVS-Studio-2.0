# FPVS Studio v1 Architecture Reference

The [original v1 specification](references/archive/FPVS_Studio_v1_Architecture_Spec.md)
is historical design context. It is no longer the current model, hardware or workflow
contract. This compatibility pointer preserves existing links.

For current work, use [the package map](../ARCHITECTURE.md) and select one scope in
[the task index](agent/agent-index.md). Product categories live in
[Experiment categories](EXPERIMENT_CATEGORIES.md); compiled behavior lives in
[RunSpec](RUNSPEC.md), [SessionPlan](SESSION_PLAN.md) and
[Runtime execution](RUNTIME_EXECUTION.md).

The oddball marker remains `55` by default. Nonstandard markers require explicit
user direction and `allow_nonstandard_oddball_trigger_code`; the current RunSpec
contract owns that rule.
