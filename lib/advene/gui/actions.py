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
