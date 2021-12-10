#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2021 Olivier Aubert <contact@olivieraubert.net>
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Gio.Action related helpers
"""
import logging
logger = logging.getLogger(__name__)

#
# Note: this code is adapted from
# https://github.com/gaphor/gaphor/
#
# Copyright 2001-2021 Arjan Molenaar & Dan Yeaw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# This license is applicable for all gaphor resources, unless specified
# otherwise.

from enum import Enum
from gi.repository import Gio
from gi.repository import GLib
from typing import get_type_hints

class Variant(Enum):
    str = GLib.VariantType.new("s")
    int = GLib.VariantType.new("i")
    bool = GLib.VariantType.new("b")

def as_variant_type(t):
    if t is None:
        return None
    elif t is str:
        return Variant.str.value
    elif t is int:
        return Variant.int.value
    elif t is bool:
        return Variant.bool.value
    else:
        raise ValueError(f"No GVariantType declared for Python type {t}")

def to_variant(v):
    if v is None:
        return None
    elif isinstance(v, str):
        return GLib.Variant.new_string(v)
    elif isinstance(v, bool):
        return GLib.Variant.new_boolean(v)
    elif isinstance(v, int):
        return GLib.Variant.new_int32(v)
    else:
        raise ValueError(
            f"No GVariant mapping declared for Python value {v} of type {type(v)}"
        )

def from_variant(v):
    if v is None:
        return None
    elif Variant.str.value.equal(v.get_type()):
        return v.get_string()
    elif Variant.int.value.equal(v.get_type()):
        return v.get_int32()
    elif Variant.bool.value.equal(v.get_type()):
        return v.get_boolean()
    else:
        raise ValueError(f"No Python mapping declared for GVariant value {v}")

def menuitem_new(label, action_name=None, parameter=None):
    """Helper function to build a new menuitem with an action an a parameter
    """
    item = Gio.MenuItem.new(label, action_name)
    if parameter is not None:
        item.set_attribute_value("target", to_variant(parameter))
    return item

REGISTERED_ACTIONS = {}
class named_action:
    """Decorator. Turns a regular function (/method) into a full blown Action
    class.

    >>> class A:
    ...     @action(name="my_action", label="my action")
    ...     def myaction(self):
    ...         print("action called")
    >>> a = A()
    >>> a.myaction()
    action called
    >>> is_action(a.myaction)
    True
    >>> for method in dir(A):
    ...     if is_action(getattr(A, method, None)):
    ...         print(method)
    myaction
    >>> A.myaction.__action__.name
    'my_action'
    >>> A.myaction.__action__.label
    'my action'
    """

    def __init__(
        self, name, label=None, tooltip=None, icon_name=None, shortcut=None, state=None
    ):
        self.scope, self.name = name.split(".", 2) if "." in name else ("win", name)
        self.label = label
        self.tooltip = tooltip
        self.icon_name = icon_name
        self.shortcut = shortcut
        self.state = state
        self.arg_type = None
        self.function = None
        REGISTERED_ACTIONS[self.detailed_name] = self

    @property
    def detailed_name(self):
        return f"{self.scope}.{self.name}"

    def __call__(self, func):
        type_hints = get_type_hints(func)
        if "return" in type_hints:
            del type_hints["return"]
        if len(type_hints) >= 1:
            # assume the first argument (exclusing self) is our parameter
            self.arg_type = next(iter(type_hints.values()))
        func.__action__ = self
        self.function = func
        return func


def is_action(func):
    return hasattr(func, "__action__")

def _action_activate(action, param, obj, name):
    na = REGISTERED_ACTIONS.get(name, None)
    if na is None:
        logger.error(f"Cannot find named action: {name}")
        return
    method = na.function
    if param is not None:
        method(obj, from_variant(param))
        if action.get_state_type():
            action.set_state(param)
    else:
        method(obj)

def create_gio_action(action, provider, attrname):
    if action.state is not None:
        state = action.state(provider) if callable(action.state) else action.state
        a = Gio.SimpleAction.new_stateful(
            action.name, as_variant_type(action.arg_type), to_variant(state)
        )
        a.connect("change-state", _action_activate, provider, attrname)
    else:
        a = Gio.SimpleAction.new(action.name, as_variant_type(action.arg_type))
        a.connect("activate", _action_activate, provider, attrname)
    return a

def register_named_actions(app):
    """Register application actions
    """
    for attrname, action in REGISTERED_ACTIONS.items():
        a = create_gio_action(action, app, attrname)
        app.add_action(a)
        if action.shortcut:
            app.set_accels_for_action(f"{action.scope}.{action.name}", [action.shortcut])
