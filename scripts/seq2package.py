#! /usr/bin/env python

"""Convert a sequence to advene annotations.

Simple script to convert a sequence of annotation as a text file to an
advene package part.

The text file has the following format :

0:15 1:57 Matin
1:58 4:49 Mme Arpel fait le menage
4:50 5:59 Embouteillages
6:00 13:14 Derriere l'usine.
13:15 16:05 Sortie de l'ecole
16:06 19:19 Visite a Mme Arpel
19:20 20:42 Soir. M. Arpel rentre.
20:43 22:59 Lendemain matin, les enfants courent vers l'ecole.
23:00 25:14 Usine Plastac
25:15 25:59 Hulot arrive a l'usine
26:00 28:31 Hulot marche dans la peinture blanche
28:32 37.19 Villa Arpel
37:20 38:19 Hulot et son neveu arrivent dans le vieux quartier.
"""


import re

def ts2ms(ts):
    (m,s) = ts.split(":")
    m = long(m)
    s = long(s)
    return (60*m + s) * 1000

f=open("seq.txt", 'r')
regexp=re.compile('(\d+:\d+)\s(\d+:\d+)\s(.*)')

for l in f:
    m=regexp.match(l)
    if m:
        (t1, t2, data) = m.groups()
    begin=ts2ms(t1)
    end=ts2ms(t2)
    print """<annotation type='#sequence' id='i%s%s'>
      <millisecond-fragment begin='%s' end='%s'/>
      <content>%s</content>
    </annotation>    
    """ % (begin, end, begin, end, data)

