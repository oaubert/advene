/* gcc -g -Wall -W pangohack.c -nostartfiles -shared -fPIC -Wl,-soname,pangohack.so.0 -o libpangohack.dylib */

/* gcc -o libpangohack.dylib -dynamiclib pangohack.c -Wall -Wl,-v */
/*
  Copyright (C) Tollef Fog Heen <tfheen@canonical.com> 

  Modified by Olivier Aubert <olivier.aubert@liris.cnrs.fr>

  Based on code copyright (C) 2002 Per Kristian Gjermshus <pergj@ifi.uio.no>

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
*/
#include <stdlib.h>
#include <stdio.h>

const char * pango_get_sysconf_subdirectory (void) {
  char * d;

  d = getenv("PANGO_SYSCONF_DIR");
  if ( ! d )
      d = "/etc/pango32";
  fprintf(stderr, "Pangohack: using sysconf dir %s\n", d);
  return d;
}

const char * pango_get_lib_subdirectory (void) {
  char * d;

  d = getenv("PANGO_LIB_DIR");
  if ( ! d )
      d = "/usr/lib32/pango";
  fprintf(stderr, "Pangohack: using lib dir %s\n", d);
  return d;
}
