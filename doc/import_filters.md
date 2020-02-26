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

## How to test them

You can launch import filters either from the GUI, or from the command line.

From the GUI, open a video file or a package, then go to `File/Import`
file...  In the subsequent dialog, you can choose a file to process
and the interface will display a list of possible import filters for
the given file.

There is a shortcut to this feature, to apply filters that are
processing video file to the currently loaded video: the `File/Process
video` will display a simple dialog asking you to pick the appropriate
filter.

From the command-line, you can launch the `util.importer` module as a
script:

    PYTHONPATH=./lib python3 ./lib/advene/util/importer.py "Dominant color importer" /full/path/to/video.mp4 /tmp/test.xml

To get the list of valid filter names, simply call the `util.importer`
module without any parameter.

The last parameter is the name of the package that will be saved with
the output. If you omit it, the produced annotations will be dumped as
json on stdout.
