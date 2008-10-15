"""
Cinelab Application Model
=========================

This is the canonical example of specializing the CORE model API
(`advene.model.core`) into a specific application model.

Note that two kinds of additional behaviours should be distinguished when
extending the core model:

    # creation of additional elements or information in the model: this kind of
    behaviour is usually to be skipped by the *parser*, since the additional
    elements or information will later be normally serialized. This kind of
    behaviour *must* be implemented using *events* (`advene.model.events`),
    since parsers explicitly inhibit events.

    # integrity checking and other behaviour: this kind of behaviour should
    always be enforced, including in the parser. They must therefore *not rely*
    on events, but rather on overriding methods.
"""
