* Purpose of the software

The Advene project (Annotate Digital Video, Exchange on the NEt) aims
at providing a model and a format to share annotations about digital
video documents (movies, courses, conferences...), as well as tools to
edit and visualize the hypervideos generated from both the annotations
and the audiovisual documents.  

Teachers, moviegoers, etc. can use them to exchange multimedia
comments and analyses about video documents. The project also aims at
studying the way that communities of users (teachers, moviegoers,
students...) will use these self-publishing tools to share their
audiovisual "readings", and to envision new editing and viewing
interfaces for interactive comment and analysis of audiovisual
content.

* Design

The software consists in a graphical user interface, integrating a
video player and an embedded webserver. The graphical user interface
is both the authoring and visualisation environment for hypervideos.

The application allows to :
  - create annotations linked to specific fragments of a video
  - link annotations through relations
  - structure annotations and relations through user-defined
    annotation-types and relation-types
  - query the annotations
  - specify rendering templates (called views) for the metadata and
    audiovisual document, which qualify as hypervideos.

All necessary metadata is stored in files called packages, that can be
exchanged independently from the audiovisual document.

Three categories of hypervideos are available in Advene: static views,
dynamic views and adhoc-views.

Static views are X(HT)ML templates that, applied on the annotations,
generate a HTML document. The HTML document is served through the
embedded webserver to a standard web browser. Snapshots from the video
(extracted on the fly) can be addressed in the template. It is also
possible to control the application (video player control, adhoc view
opening...).

Dynamic views are augmented video renderings, guided by the
annotations. It is possible to caption the video, control the video
behaviour (pause, change position...), etc according to the
annotations.

Adhoc-views are programmed views available from the GUI. Among
available views are a timeline, a transcription view synchronized with
the video...

* Basic use

Sample packages are provided on the Advene website:
http://liris.cnrs.fr/advene/examples.html

Both the Nosferatu analysis and the Ted Nelson speech analysis can be
used as tutorials to go through the Advene features.

A user manual is also available:
http://liris.cnrs.fr/advene/wiki/index.php/Main_Page
