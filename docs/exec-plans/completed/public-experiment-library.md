# Public Experiment Library

Status: Completed

## Outcome

An unconnected Studio user can find and import the Color Oddball Demo in the
existing Experiment Library. Lab members can browse authorized lab projects in
the same dialog. OpenFPVS administrators can publish and unlist exact verified
releases for public access.

## Work and checks

1. Add anonymous catalog, proof and download routes for explicitly published
   OpenFPVS releases. Verify guessed private routes, withdrawal and lab access.
2. Show Public projects and Lab projects in the shared Studio browser. Verify
   search, review, permissions, errors and import at the minimum and default
   sizes. Respect Studio's reduced-motion preference.
3. Build a two-condition Color Oddball Demo with an editable project and original
   stimuli. Verify import, six runs and 48 cycles per run at supported refresh
   rates, and verify the exact release bytes before activating public access.

Use the [Library contract](../../EXPERIMENT_LIBRARY.md) for current behavior.

## Verification

- On November 16, 2026, OpenFPVS deployed migration `0029_public_library.sql`
  and Worker version `7d86fe73-34a3-4384-97e7-26a2832eb6da`. The signed-out site
  showed Color Oddball Demo 1.0.0. Anonymous lab catalog, download and provenance
  probes were denied.
- The Studio client fetched the public catalog, verified and imported the signed
  118,907-byte release, saved the public receipt and checked the installed version
  without a credential store. The import and compile test covers all six
  supported refresh targets.
- The visible Windows Library suite passed all 60 cases. The live public catalog
  rendered at 900 × 640 in Light and 1040 × 760 in Dark. Two existing Project
  Versions test failures also reproduced at the unchanged baseline.
