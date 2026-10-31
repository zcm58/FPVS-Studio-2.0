# Engine Guidance

Engines own the presentation interface, registry and PsychoPy implementation. Only
this package imports PsychoPy, lazily. Start with the relevant section of
`docs/ENGINE_INTERFACE.md`; use `docs/RUNSPEC.md` for frame/trigger contracts.

## Rendering Boundary

- Consume neutral compiled contracts and render one condition or task step at a time.
  Runtime owns session order, task validation/branches, scoring and persistence.
- Render image, word and native scene payloads without changing compiled schedules.
  Sinusoidal image contrast uses precomputed frame operations; other modes retain
  their behavior. Engine-specific types never enter project schemas or exports.
- Prepare/release resources per condition. Native scenes prepare before timed pre-tasks
  and consume the prepared cache without new warmup blanks. Do not retain stimuli
  across conditions or prepare resources after a timed scene fixation.
- Keep native graphics creation/use/cleanup on the presentation thread. Use
  `psychopy_graphics_lifetime` for foreign-thread GC/finalizers. Drain deferred cleanup
  only at untimed boundaries; release reusable text/controls on every exit path.
- Require an explicit trigger backend and external-marker capability for recording.
  Reject missing backends, empty schedules or external output in explicit Test/Pilot.
  Flip-lock markers via `callOnFlip`; exported clocks exclude warmup. Opted-in AB
  frame -1 is the neutral condition marker with a continuous stream clock.
- Keep task clocks/input separate from playback. `escape` aborts. Preserve keyboard
  and visible click submission, resolved labels and per-question input clearing.
  Native mouse handlers retain press/release events and clean up between screens.
- Export strict timing misses as QC metadata unless runtime policy requires abort.
  Transport submission never proves receiver integrity or physical EEG timing.

Use the `engine` focused route and affected fake-window/input tests. Add runtime or
compiler focused checks when touching their seams, then repo precommit for shared
behavior. Visible presentation/hardware acceptance is distinct from source tests.
