# Visual FPVS Experiment Designer

Updated: 2026-09-10. The experimental branch implements category-specific native
letter-stream and image designers. New Attentional-Blink projects use 10 Hz digits
and separate T1/T2 letters with 100/300/500 ms SOAs. Setup > Design shows shared
character pools, condition SOAs, a full 20-character cycle, an onset bracket, and a
quarter-speed illustration. Character Size edits native text height. The existing
questionnaire editor is also accessible from Design. See
[Experiment Categories](EXPERIMENT_CATEGORIES.md) for the current defaults, schema,
questionnaire interpretation, and exact display-grid requirements.

The digit field defines the available symbols, not their order. Native AB playback
samples digits randomly without immediate repeats, including across cycle boundaries.
The designer uses the same core sampler for its randomized example and draws a fresh
cycle during the slowed preview. **Shuffle example** changes only the illustration;
it does not edit the project or run seed. T1/T2 positions and SOAs stay fixed while
symbol identities vary. The run seed makes experimental playback reproducible.

T1 and T2 each have a color swatch with the current hex value. Select the swatch to
open the visual color picker, choose a color or enter its exact hex value, then
confirm. Cancel leaves the current color unchanged. Accepted choices update the
timeline draft; Next applies them to all study conditions. If T2 is no longer white,
update the post-condition question and participant instructions to match.

Image design is available only for **FPVS Oddball Paradigm**. **Standard FPVS** is
a disabled Coming soon placeholder. Attentional-Blink image pairs and their ISI editor
are retired. Old files remain readable but cannot be authored, compiled or run; see
[Experiment Categories](EXPERIMENT_CATEGORIES.md).

## Oddball Image Designer

Setup > Conditions edits names, modality, instructions and tasks. Setup > Design
embeds `ExperimentDesignerWidget` at a `1000x600` content budget inside the nine-step
`1120x820` wizard. The optional standalone dialog hosts the same editor. Word lists
remain in Conditions and their cadence in Timing.

Base and Oddball source cards show real thumbnails decoded on workers. Drag or click
a source tile to add a role; separate folder buttons import into fresh project-owned
source sets without merging images or adding slots. Full paths are accessible through
tooltips. Windows extended-length filesystem paths preserve original image names and
bytes without changing persisted project-relative paths.

The timeline shows equal-duration slots. Cadence is a typed numeric field without
arrow/wheel stepping. Keyboard/context actions also move and remove slots. Preview
at quarter speed illustrates the cycle; 50% Blank previews image and blank phases,
while Contrast Modulation discloses that its slowed preview omits modulation.
Timing & display details calculates frames without changing the selected real display.

Next applies the draft cycle and cadence; standalone Use this design does the same.
Saving remains explicit. Invalid or incomplete sources block progression with inline
guidance. Discard restores timing while preserving imported source files.

Imports block navigation while mutating sources. Thumbnail decoding can coexist with
applying valid settings, but editor disposal waits for workers. Hidden embedded editors
defer decoding until shown. All Setup pages use the shared frameless surface and
bottom navigation without a separator line.

## Ownership and Verification

`core/experiment_design.py` owns oddball cycle mathematics.
`core/attentional_blink_stream.py` and `core/compiler_attentional_blink_stream.py` own
native AB character scheduling. Category validation, authoring and runtime guards
reject retired image-pair records without converting or deleting assets.

Registered designer, category, native-stream and wizard tests cover folder hit targets,
pending drafts, workers, exact SOA counts, supported templates and light/dark geometry.
Visible Qt checks require user authorization. No authoring check replaces physical
presentation/trigger verification on the study computer.

The research notes below are background, not additional supported designer modes.

## Evidence That Constrains the Design

An arbitrary second picture is not guaranteed to suppress the first. Target/mask
contrast, duration, composition and spatial relationship matter. Spatially adjacent,
nonoverlapping metacontrast differs from an overlapping pattern mask; masking
functions can have different shapes rather than a universal monotonic recovery.
Choose and pilot the actual assets against the intended target task.
[Öğmen et al., 2006](https://pubmed.ncbi.nlm.nih.gov/17081585/).

FPVS already has relevant timing evidence. Retter and colleagues compared 50-ms
images with 50-ms blanks at 10 Hz, 100-ms images without blanks at 10 Hz, and 50-ms
images without blanks at 20 Hz, while faces remained at 1 Hz. This separates some
duration, gap and rate comparisons; it does not validate a dedicated target-mask
pair or supply an invisibility threshold.
[Retter et al., 2018, author manuscript](https://dial.uclouvain.be/pr/boreal/object/boreal:222114/datastream/PDF_01/view).

Frequency-tagged discrimination is not automatically successful identity recognition
or subjective awareness. A face-category response answers a different question from
recognizing a particular face. Retter et al. related neural responses to behavioral
categorization and explicitly distinguished categorization from extracting all face
information. [Retter et al., 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7339021/).
More recent work related frequency-tagged face signals to correct gender reports,
visibility and confidence under specific contrast conditions; those behavioral
measurements established the relationship rather than assuming it from amplitude.
[Mazancieux, Cleeremans & de Heering, 2026, abstract](https://pubmed.ncbi.nlm.nih.gov/41934781/).

Accordingly, define “recognition” before testing: category discrimination, identity
recognition, or visibility. Include an appropriate behavioral task, potentially in
matched separate blocks so responses do not interrupt the periodic train. Do not
label the preview's expected EEG outcome “recognized” or “unrecognized.” A nonsignificant
frequency response alone is not proof of absent recognition.
