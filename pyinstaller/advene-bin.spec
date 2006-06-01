Summary: Annotate DVDs, Exchange on the NEt! (binary version)
Name: advene-bin
Version: 0.21
Release: 1
License: GPL
Packager: Olivier Aubert <olivier.aubert@liris.cnrs.fr>
Group: Video
URL: http://liris.cnrs.fr/advene/
Source: http://liris.cnrs.fr/advene/download/
Buildroot: FIXME

%define _rpmdir ../
%define _rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm
%define _unpackaged_files_terminate_build 0

%description
The Advene (Annotate DVd, Exchange on the NEt) project is aimed
towards communities exchanging discourses (analysis, studies) about
audiovisual documents (e.g. movies) in DVD format. This requires that
audiovisual content and hypertext facilities be integrated, thanks to
annotations providing explicit structures on  audiovisual streams, upon
which hypervideo documents can be engineered.

The Advene framework provides models and tools allowing to design and reuse
annotations schemas; annotate video streams according to these schemas;
generate and create Stream-Time Based (mainly video-centred) or User-Time
Based (mainly text-centred) visualisations of the annotations. Schemas
(annotation- and relation-types), annotations and relations, queries and
views can be clustered and shared in units called packages. Hypervideo
documents are generated when needed, both from packages (for annotation and
view description) and DVDs (audiovisual streams).

# %prep
# %setup -q
# 
# %build
# make RPM_OPT_FLAGS="$RPM_OPT_FLAGS"
# 
# %install
# [ "%{buildroot}" != '/' ] && rm -rf %{buildroot}
# make install DESTDIR=%{buildroot}
# 
# %clean
# rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
# %{_bindir}/advene-bin
# %dir %{_libdir}/advene-package
