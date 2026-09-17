# Developer tools

This package ships in normal builds. Settings > Advanced owns the password-gated
opt-in; `mode.DeveloperMode` captures activation once at controller startup. Changing
its saved preference requires a restart. Keep it outside project/execution contracts.

- Core `library_publish.prepare_library_bundle` owns clean project preparation.
- `catalog_publisher.py` owns GitHub credentials, authorization, HTTP uploads and
  catalog commits. The private service CLI delegates here; keep one implementation.
- The developer password controls UI exposure only. GitHub account `zcm58` and write
  permission on the fixed private repository authorize publishing. Never distribute
  GitHub credentials, service App keys, invitation codes or device tokens.
- Resolve maintainer credentials from existing noninteractive Git credentials or
  explicit GH_TOKEN, only in workers. Never log tokens or raw external errors.
- Access checks, preparation, publishing and disposal belong in app-owned workers.
  Cancel between requests/upload reads; shutdown waits for bounded active requests.
- Preparation never changes the project. Retain exact prepared bytes on remote
  failure/cancellation; retry reconciles an uncertain publication.
- Delete only generated directories registered to this service instance, rejecting
  links/reparse points and changed ownership. Never clean the source or private repo.

See docs/EXPERIMENT_LIBRARY.md. Run the Library focused route and publisher/mode
unit tests; GUI execution remains an explicit visible opt-in.
