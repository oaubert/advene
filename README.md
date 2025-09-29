Advene video annotation software
================================

[![Build Status](https://github.com/oaubert/advene/workflows/packaging/badge.svg?branch=master)](https://github.com/oaubert/advene/actions/workflows/packaging.yml?query=branch%3Amaster)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1003149.svg)](https://doi.org/10.5281/zenodo.1003149)
![License: GPL2.0](https://img.shields.io/github/license/oaubert/advene)
[![Project homepage](https://img.shields.io/badge/Project%20homepage-advene.org-ff0080)](https://advene.org)

The cross-platform Advene (Annotate Digital Video, Exchange on the
NEt) application allows users to easily create comments and analyses
of video documents, through the definition of time-aligned annotations
and their mobilisation into automatically-generated or user-written
comment views (HTML documents). Annotations can also be used to modify
the rendition of the audiovisual document, thus providing virtual
montage, captioning, navigation... capabilities. Users can exchange
their comments/analyses in the form of Advene packages, independently
from the video itself.

The Advene project aims at providing a model and a format to share
annotations about digital video documents (movies, courses,
conferences...), as well as tools to edit and visualize the
hypervideos generated from both the annotations and the audiovisual
documents.

With the Advene software, teachers, moviegoers, etc. can exchange
multimedia comments and analyses about video documents. The project
also aims at studying the way that communities of users (teachers,
moviegoers, students...) will use these self-publishing tools to share
their audiovisual "readings", and to envision new editing and viewing
interfaces for interactive comment and analysis of audiovisual
content.

Design
======

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
(extracted on the fly) can be used in the template. It is also
possible to control the application (video player control, adhoc view
opening...) though URLs.

Dynamic views are augmented video renderings, guided by the
annotations. It is possible to caption the video, control the video
behaviour (pause, change position...), etc according to the
annotations.

Adhoc-views are programmed views available from the GUI. Among
available views are a timeline, a transcription view synchronized with
the video...

Basic use
=========

Sample packages are provided on the Advene website:

 http://advene.org/examples.html

Both the Nosferatu analysis and the Ted Nelson speech analysis can be
used as tutorials to go through the Advene features.

A user manual is also available at:

http://advene.org/wiki/

Copyright Information
=====================

This software is covered by the GNU General Public Licence
(version 2, or if you choose, a later version).
