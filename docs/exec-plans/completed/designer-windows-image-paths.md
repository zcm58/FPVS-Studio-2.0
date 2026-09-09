# Designer Windows Image Paths

Status: Completed

## Reproduced problem

The designer's fresh T2 source directory makes an imported image path 276 characters
long under the user's OneDrive project root. The supplied Python runtime raises
FileNotFoundError for ordinary copying and Pillow reading at that length, even though
the source is readable and the destination directory exists. An isolated fixture
reproduced the error twice; Windows extended-length access succeeds on the same file.

## Fix and boundaries

Keep original image filenames, contents and persisted project-relative paths.
Add one core-owned filesystem-path adapter for Windows I/O. Normalize absolute drive
and UNC paths before adding the extended namespace. Project containment validation
and relative serialization must accept ordinary and extended paths consistently.
Use the adapter through image intake/inspection, normalization/derivatives, thumbnail
decoding and downstream asset checks. No registry changes or source-project edits.

## Verification

- Reproduce failure before edits using the reported filename and equivalent path length.
- Verify import, reinspection, manifest/compile, normalization, derivatives and thumbnail
  decoding retain all images and original content at paths longer than 260 characters.
- Cover namespace idempotence, UNC conversion, Unicode and containment in focused tests.
- Run focused routes, relevant visible GUI coverage (already authorized by the user),
  and shared-code precommit checks. Report existing unrelated failures separately.

## Progress

- Reproduction and cause confirmed in the actual `.venv3.10` runtime. The original
  reproduction passed twice after the fix. An isolated import of 18 existing project
  images also preserved every filename and SHA-256 digest.
- Added the core filesystem adapter and used it through intake, image transforms,
  thumbnail enumeration, compilation and preflight. Persisted project and compiled
  image paths remain relative POSIX paths without Windows namespace prefixes.
- Added regression coverage for long directories and filenames, manifest and folder
  discovery, image decoding and simulated playback preparation. Namespace, Unicode,
  relative serialization and containment cases pass.
- Focused verification passed: core 252 passed / 1 unavailable-symlink skip;
  preprocessing 23 passed; repository 32 passed. The full safe suite passed with
  1,163 tests and 5 unavailable-symlink skips. The user-approved visible designer
  suite passed all 54 tests. No experimental presentation or hardware triggers ran.
- Shared-code precommit Ruff and compilation passed. Its mypy step remains blocked
  by the existing unrelated `gui/controller.py:372` return-type error; changed path
  and image-processing files passed targeted mypy checks.
- Removed the two task-created diagnostic fixture directories. User project files,
  original source folders and Windows settings were not changed.
