import xml.dom.ext

TEXT_NODE = xml.dom.Node.TEXT_NODE
ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE

def printElementSource(element, stream):
#    doc = element._get_ownerDocument()
#    df = doc.createDocumentFragment()
#    for e in element._get_childNodes():
#        df.appendChild(e.cloneNode(True))
#    xml.dom.ext.Print(df, stream)
    for e in element._get_childNodes():
        xml.dom.ext.Print(e, stream)

def printElementText(element, stream):
    if element._get_nodeType() is TEXT_NODE:
        # Note: element._get_data() returns a unicode object
        # that happens to be in the default encoding (iso-8859-1
        # currently on my system). We encode it to utf-8 to
        # be sure to deal only with this encoding afterwards.
        stream.write(element._get_data().encode('utf-8'))
    elif element._get_nodeType() is ELEMENT_NODE:
        for e in element._get_childNodes():
            printElementText(e, stream)
