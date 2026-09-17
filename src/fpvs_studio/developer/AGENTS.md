# Developer tools

This package is an explicit source-checkout maintainer surface, excluded from frozen
builds. `FPVS_LIBRARY_PUBLISHER_REPO` must name a private Library service checkout.

- Core `library_publish.prepare_library_bundle` owns clean project preparation.
- The configured private repository's `scripts/publish-catalog.py` owns GitHub
  credentials, authorization, HTTP uploads and catalog commits. Do not duplicate
  those operations or read credentials in Studio.
- Check the configured checkout's exact GitHub remote before executing its script.
  Use bounded temporary output capture and timeouts, no shell, and no visible consoles.
- Access checks, preparation, publishing and disposal belong in GUI workers.
- Preparation never changes the project. Retain exact prepared bytes on remote
  failure or cancellation; a retry can reconcile an uncertain publication.
- Delete only the generated directory registered to this service instance, rejecting
  links/reparse points and changed ownership. Never clean the source or private repo.

See `docs/EXPERIMENT_LIBRARY.md`. Run developer-publisher unit coverage and the
Library focused verification route; GUI execution remains an explicit visible opt-in.
