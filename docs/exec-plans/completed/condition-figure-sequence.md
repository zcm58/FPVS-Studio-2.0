# Condition Figure stimulus sequence

Status: Completed

In **Tools > Condition Figure**, use Automatic to fill the illustrated slots
from the condition's configured pools without reusing a stimulus across the
strip. Mark slots that lack an unused example. Keep the existing Manual
selection workflow. Prepare the automatic sequence in the source-loading worker
and use that same sequence for the dialog previews and export.

For 50% blank conditions, use independent base and oddball tracks and center
each raised half-cycle beneath its stimulus. Preserve the rate and oddball
timing labels and the other presentation modes.

Non-Qt tests cover unique selection, missing examples, and pulse alignment.
Registered Qt smoke coverage checks preview and export agreement. The five
Creatine exports each contain 12 distinct image tiles at 600 dpi. The three
50% blank figures show separate base and oddball pulses.
