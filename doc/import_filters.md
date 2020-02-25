# Writing import filters

Advene implements a generic import filter API, to ease developing. The
general principle is that it takes some parameters as input, and
outputs annotations.

The main API is implemented in `advene/util/importer.py`. See the
docstring at the beginning of the module for an overview of how it
works.

Some most specific APIs have been defined to ease development:

`advene.util.importer.ExternalAppImporter` simplifies the integration
of an external application that produces data on its stdout. See
`advene.plugins.shotdetectapp` for an example of how to use it.

`advene.util.gstimporter.GstImporter` simplifies the writing on
filters relying on the Gstreamer pipeline. See the docstring of the
`GstImporter` class for information.  You can see examples of usage in
the `plugins.soundenveloppe` plugin (for audio, using Gstreamer
message metadata) and `plugins.dominantcolor` (for video, using frame
data).
