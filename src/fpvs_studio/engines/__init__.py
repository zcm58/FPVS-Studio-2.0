"""Presentation-engine package for swappable runtime renderers.
It groups the engine interface, registry, and PsychoPy-backed implementation that consume RunSpec while runtime owns SessionPlan flow.
Only this layer may touch PsychoPy, and those imports remain inside engine implementation code."""
