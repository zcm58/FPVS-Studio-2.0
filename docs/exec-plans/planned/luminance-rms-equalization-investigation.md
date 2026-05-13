# Luminance And RMS Contrast Equalization Investigation

Status: Planned

## Summary

Investigate how FPVS Studio should support stimulus luminance and RMS contrast
equalization for users who want preprocessing closer to common Rossion-style methods.

## Investigation Questions

- Which equalization algorithm should be used for RGB and grayscale images?
- Should equalization run during project-linked condition normalization, in the standalone
  Image Resizer, or both?
- What provenance should be written to the stimulus manifest for equalized outputs?
- What validation or preview is needed so users can trust the transformed images?
- Which dependencies are acceptable for a packaged Windows build?

## Implementation Boundary

This plan is an investigation first. Do not add equalization controls until the algorithm,
output format, manifest metadata, and verification strategy are decided.

## Test Strategy To Define

- Numerical tests for target luminance and RMS contrast on synthetic images.
- Regression tests on a small fixture set with known expected output statistics.
- Manifest tests confirming equalization parameters and source hashes are recorded.
- GUI smoke tests for any future preprocessing controls.

## Assumptions

- Equalization should create project-local derived assets, not mutate original source files.
- Any future implementation must remain deterministic and reproducible from manifest
  metadata.
