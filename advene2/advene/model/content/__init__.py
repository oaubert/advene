"""
Content handlers
================

A content handler is an object (usually a module) capable of parsing a content
to a python object.

See reference implementation `advene.model.content.builtin`.

Textual content
===============

The `register` module also contains a method to register mimetypes recognized
as textual contents, besides those beginning with 'text'. Indeed, some other
mimetypes (e.g. 'image/svg') can be handled by text-based tools. Those
registered mimetypes are used by the `content_is_textual` property.

Registered mimetypes can be generic (i.e. use *).
"""
