"""Trigger backend package for optional hardware integrations.
These modules expose a small abstraction that runtime can call while keeping RunSpec, SessionPlan, and execution contracts hardware-neutral.
The package owns backend interfaces only; experiment logic and export schemas remain in core and runtime."""
