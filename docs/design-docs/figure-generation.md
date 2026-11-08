# Figure generation standard

Use these defaults for FPVS Studio and FPVS Toolbox figures created by tools or
agents. Apply a documented journal or tool profile when the intended venue or
workflow specifies its own typography, layout, or formats.

## Layout and lettering

- Plan the placed width before laying out the figure. Use 89 mm for a single
  column or 183 mm for a double column. Use 183 mm for wide stimulus strips.
- Center a short, meaningful condition title above the figure when it helps
  identify the panel. Omit subtitles, tool names, and repeated explanations.
  Keep methods and captions outside the artwork. Keep units, missing-data
  labels, and annotations needed to interpret the figure.
- Use one sans-serif family throughout. Studio uses its bundled Open Sans.
  Arial and Helvetica are preferred when matching Nature's final artwork.
  At the placed width, use 7 pt titles, 6 pt axis and legend labels, and
  5 pt ticks and essential notes. Use lowercase 8 pt bold letters for multipanel
  labels.
- Use dark lettering on white and color the plotted marks or legend swatches.
  Put the legend below the plot when it keeps the figure compact. Distinguish
  series by position, marker, or line style as well as color. Keep axis labels
  and units legible, use strokes around 0.25–1 pt at placed size, and keep
  unnecessary gridlines and decoration out of the artwork.

The page widths, lettering range, and accessibility rules follow
[Nature's figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/).
The stroke range follows [Nature's line-weight guidance](https://research-figure-guide.nature.com/figures/extended-data-formatting-guidelines/#line-weights).

## Export and verification

- Export rasters, including generated raster layers in vector files, at
  **600 dpi or higher** at the intended physical size. This is the FPVS export
  floor. Size each pixel dimension for the placed length in inches multiplied
  by the export DPI, then verify the pixel dimensions and density metadata in
  the saved file. Check the effective resolution of source images separately
  and report limited source detail.
- When the tool supports editable artwork, retain embedded fonts and editable
  text and lines in the vector export. Use the venue's requested formats for
  final submission. [Nature's artwork specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/).
- Use configured timing and source data for rates, stimulus roles, units, and
  conditions. Keep representative schematics distinct from measurements.
- Inspect the exported file at its placed size. Check long labels, crowded
  ticks, legend fit, and series distinguishability in grayscale. Verify a
  typical figure and any changed edge case through the normal export path.

Studio renderers reuse `src/fpvs_studio/tools/figure_style.py` for raster DPI,
font, lettering sizes, and conversion from placed points to export pixels.
Toolbox uses its own shared export style module. Use the applicable app's
existing export path and verification scope.
