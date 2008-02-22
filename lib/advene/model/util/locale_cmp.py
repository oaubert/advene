#
# This file is part of Advene.
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
import locale

from choice_tree import ChoiceTree

try:
    import xml.dom
except ImportError:
    pass


class Locale (object):
    """Class for representing and comparing locale settings.
    """

    def __init__ (self, a_string):
        self.lang = None
        self.country = None

        if a_string is not None and len (a_string) >= 2:
            self.lang = a_string[0:2]
            if len (a_string) >= 5:
                self.country = a_string[3:5]

        self.__hash = hash (str (self))

    def fromDomElement (elt):
        s = elt.getAttributeNS (xml.dom.XML_NAMESPACE,'lang')
        return Locale (s)
    fromDomElement = staticmethod (fromDomElement)

    def fromEnv ():
        return Locale (locale.getdefaultlocale ()[0])
    fromEnv = staticmethod (fromEnv)


    def isMoreSpecificThat (self, other):
        if other.lang is None:
            return True
        else:
            if self.lang == other.lang and other.country is None:
                return True
            else:
                return False

    def isMoreGeneralThat (self, other):
        return other.isMoreSpecificThat (self)

    def __eq__ (self, other):
        try:
            return self.lang == other.lang and self.country == self.country
        except AttributeError:
            pass
        return False


    def __str__ (self):
        if self.lang is None:
            r = ''
        elif self.country is None:
            r = self.lang
        else:
            r = '%s_%s' % (self.lang, self.country)
        return r

    def __repr__ (self):
        return "Locale('%s')" % str (self)

    def __hash (self):
        return self.__hash

#nullLocale = Locale('')
defaultLocale = Locale.fromEnv ()

class LocaleChooser (object):
    """
    A tree of element stored hierarchically with respect to their locale.
    The =getBestFit= method returns the best fit element with respect to the
    default locale.
    """

    def __init__ (self):
        self.__ct = ChoiceTree ()

    def __loc2tuple (self, loc):
        if loc.lang is None:
            return ()
        elif loc.country is None:
            return (loc.lang,)
        else:
            return (loc.lang, loc.country)

    def add (self, elt):
        seq = self.__loc2tuple (Locale.fromDomElement (elt))
        self.__ct.set (seq, elt)

    def getBestFit (self, loc = defaultLocale):
        seq = self.__loc2tuple (loc)
        tree = self.__ct
        exactMatch = None
        try:
            subtree = tree.getSubtree (seq)
            exactMatch = subtree.getAnyInstance ()
        except KeyError:
            pass
        return (
          exactMatch or
          tree.getMostSpecificInstance (seq) or
          tree.getAny ()
        )
