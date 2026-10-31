# Preprocessing Guidance

Preprocessing owns source-image intake, inspection, normalization, deterministic
assets and manifests. `models.py` owns `StimulusManifest` and related records;
`manifest.py` persists/query them. Core consumes serialized neutral provenance.

- Condition sources accept case-insensitive JPG/JPEG/PNG. Launchable sets have known,
  uniform resolution; rectangles and different Base/Oddball resolutions are supported.
  Mixed-size sets require explicit project-local normalization, never silent resizing.
- Generated derivatives are project-contained PNGs. `original` preserves imported
  bytes, `grayscale` converts luminance, `rot180` rotates (not inverts), and
  `phase_scrambled` records its reproducible seed/parameters.
- Manifests retain source/derived hashes, paths, geometry, format, transform chain,
  seeds, versions and timestamps. Identical source/parameters/seed must reproduce
  the same derivative.
- Standalone Image Resizer may also read BMP/TIF/TIFF, writing separate PNG copies
  without mutating project sets/manifests.
- `inspection.validate_image_files` owns bundle content checks: matching format,
  single-frame complete decode, 64 MiB encoded/decoded buffers, 8192 pixels per axis
  and 16,777,216 pixels total. Decoder overhead is additional; cancellation occurs
  between decode phases. These limits are not a malware sandbox. Library publishing
  retains its narrower JPG/PNG policy; see `docs/EXPERIMENT_LIBRARY.md`.
- No Qt, PsychoPy, runtime or engine-specific contracts. Do not move image work into
  compiler/runtime; use neutral core path/serialization helpers.

Run the `preprocessing` focused route and relevant inspection/manifest/transform tests.
