/*****************************************************************************
 *
 * Sarissa XML library version 0.9 rc1
 * Copyright (c) 2003 Manos Batsis, mailto: mbatsis@netsmart.gr
 * See the Sarissa homepage at http://sarissa.sourceforge.net for more
 * information
 *
 * This software is subject to the provisions of the Zope Public License,
 * Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
 * THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
 * WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
 * FOR A PARTICULAR PURPOSE.
 *
 *****************************************************************************/

// $Id: sarissa.js,v 1.1 2004/01/16 15:32:53 oaubert Exp $

// some basic browser detection
var _SARISSA_IS_IE = (navigator.userAgent.toLowerCase().indexOf("msie") > -1)?true:false;
var _SARISSA_IS_MOZ = (document.implementation && document.implementation.createDocument)?true:false;
var _sarissa_iNsCounter = 0;
var _SARISSA_IEPREFIX4XSLPARAM = "";
if (_SARISSA_IS_MOZ)
{
	//============================================
	// Section: Factory methods for Moz
	//============================================
	/**
	 * Factory method to obtain a new DOM Document object.
	 * @argument sUri the namespace of the root node (if any)
	 * @argument sUri the local name of the root node (if any)
	 * @returns a new DOM Document
	 */
	Sarissa.getDomDocument = function(sUri, sName)
	{
		var oDoc = document.implementation.createDocument(sUri, sName, null);
		oDoc.addEventListener("load", _sarissa__XMLDocument_onload, false);
		return oDoc;
	};
	/**
	 * Factory method to obtain a new XMLHTTP Request object
	 * @returns a new XMLHTTP Request object
	 */
	Sarissa.getXmlHttpRequest = function()
	{
		return new XMLHttpRequest();
	};
	//============================================
	// Section: utility functions for internal use
	//============================================
	/**
	 * Attached by an event handler to the load event. Internal use.
	 */
	function _sarissa__XMLDocument_onload()
	{
		_sarissa_loadHandler(this);
	};
	/** 
	 * Ensures the document was loaded correctly, otherwise sets the parseError to -1
	 * to indicate something went wrong. Internal use.
	 */
	function _sarissa_loadHandler(oDoc)
	{
		if (!oDoc.documentElement || oDoc.documentElement.tagName == "parsererror")
			oDoc.parseError = -1;
		_sarissa_setReadyState(oDoc, 4);
	};
	/**
	 * Sets the readyState property of the given DOM Document object. Internal use.
	 * @argument oDoc the DOM Document object to fire the readystatechange event
	 * @argument iReadyState the number to change the readystate property to 
	 */
	function _sarissa_setReadyState(oDoc, iReadyState) 
	{
		oDoc.readyState = iReadyState;
		if (oDoc.onreadystatechange != null && typeof oDoc.onreadystatechange == "function")
			oDoc.onreadystatechange();
	};
	
	/**
	 * Deletes all child Nodes of the Document. Internal use.
	 */
	XMLDocument.prototype._sarissa_clearDOM = function()
	{
		while(this.hasChildNodes())
			this.removeChild(this.firstChild);
	}
	/** 
	 * Replaces the childNodes of the Document object with the childNodes of 
	 * the object given as the parameter
	 * @argument oDoc the Document to copy the childNodes from
	 */
	XMLDocument.prototype._sarissa_copyDOM = function(oDoc)
	{
		this._sarissa_clearDOM();
		// importNode is not yet needed in Moz due to a bug but it will be 
		// fixed so...
        if(oDoc.nodeType == Node.DOCUMENT_NODE || oDoc.nodeType == Node.DOCUMENT_FRAGMENT_NODE)
        {
            var oNodes = oDoc.childNodes;
            for(i=0;i<oNodes.length;i++)
                this.appendChild(this.importNode(oNodes[i], true));
        }
        else if(oDoc.nodeType == Node.ELEMENT_NODE)
            this.appendChild(this.importNode(oDoc, true));
	};
	var _SARISSA_WSMULT = new RegExp("^\\s*|\\s*$", "g");
	var _SARISSA_WSENDS = new RegExp("\\s\\s+", "g");
    /**
     * Used to "normalize" text (trim white space mostly). Internal use.
     */
	function _sarissa_normalizeText(sIn)
	{
		return sIn.replace(_SARISSA_WSENDS, " ").replace(_SARISSA_WSMULT, " ");
	}
	//============================================
	// Section: Extending Mozilla's DOM implementation 
	// to emulate IE extentions
	//============================================
    /**
	 * Parses the String given as parameter to build the document content
	 * for the object, exactly like IE's loadXML().
     * @argument strXML The XML String to load as the Document's childNodes
	 * @returns the old Document structure serialized as an XML String
     */
	XMLDocument.prototype.loadXML = function(strXML) 
	{
		_sarissa_setReadyState(this, 1);
		var sOldXML = this.xml;
		var oDoc = (new DOMParser()).parseFromString(strXML, "text/xml");
		_sarissa_setReadyState(this, 2);
		this._sarissa_copyDOM(oDoc);
		_sarissa_setReadyState(this, 3);
		_sarissa_loadHandler(this);
		return sOldXML;
	};
	 /**
     * Extends the XMLDocument class to emulate IE's xml property by actually implementing a getter for it.
     * @uses Mozilla's XMLSerializer class.
     * @returns the XML serialization of the Document's structure.
     */
    XMLDocument.prototype.__defineGetter__("xml", function ()
	{
		return (new XMLSerializer()).serializeToString(this);
	});
    /**
     * Extends the Node class to emulate IE's xml property by actually implementing a getter for it.
     * @uses Mozilla's XMLSerializer class.
     * @returns the XML serialization of the Document's structure.
     */
    Node.prototype.__defineGetter__("xml", function ()
	{
		return (new XMLSerializer()).serializeToString(this);
	});
	/**
     * Ensures and informs the xml property is read only.
     */
	XMLDocument.prototype.__defineSetter__("xml", function ()
	{
		throw "Invalid assignment on read-only property 'xml'. Hint: Use the 'loadXML(String xml)' method instead. (original exception: "+e+")";
	});
	/**
     * Emulates IE's innerText (write). Note that this removes all childNodes of
     * an HTML Element and just replaces it with a textNode
     */
	HTMLElement.prototype.__defineSetter__("innerText", function (sText)
	{
		var s = "" + sText;
		this.innerHTML = s.replace(/\&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	});
	/**
     * Emulate IE's innerText (read). 
     * @returns the concatenated String representation of all text nodes under the HTML Element
     */
	HTMLElement.prototype.__defineGetter__("innerText", function ()
	{
		return _sarissa_normalizeText(this.innerHTML.replace(/<[^>]+>/g,""));
	});
    /** Emulate IE's onreadystatechange attribute */ 
    Document.prototype.onreadystatechange = null;
    /** Emulate IE's parseError attribute */
    Document.prototype.parseError = 0;
	/**
     * Emulates IE's readyState property, which always gives an integer from 0 to 4:
	 * 1 == LOADING, 
	 * 2 == LOADED, 
	 * 3 == INTERACTIVE, 
	 * 4 == COMPLETED
     */
    XMLDocument.prototype.readyState = 0;
	// NOTE: setting async to false will only work with documents 
	// called over HTTP (meaning a server), not the local file system,
	// unless you are using Moz 1.4.
	// BTW the try>catch block is for 1.4; I haven't found a way to check if the property is implemented without 
	// causing an error and I dont want to use user agent stuff for that...
    var _SARISSA_SYNC_NON_IMPLEMENTED = false; 
	try{
        /**
         * Emulates IE's async property. It controls whether loading of
         * remote XML files works synchronously or asynchronously.
         */
		XMLDocument.prototype.async = true;
        _SARISSA_SYNC_NON_IMPLEMENTED = true;
        
	}catch(e){/*trap*/}
	/** Keeps a handle to the original load() method. Internal use. */ 
	XMLDocument.prototype._sarissa_load = XMLDocument.prototype.load;
	/** 
    * Extends the load method to provide synchronous loading
	* for Mozilla versions prior to 1.4, using an XMLHttpRequest object (if async is set to false)
	* @returns the DOM Object as it was before the load() call (may be empty)
	*/
	XMLDocument.prototype.load = function(sURI)
	{
		var oDoc = document.implementation.createDocument("", "", null);
		oDoc._sarissa_copyDOM(this);
		this.parseError = 0;
		_sarissa_setReadyState(this, 1);
		try
		{
			if(this.async == false && _SARISSA_SYNC_NON_IMPLEMENTED)
			{
				var tmp = new XMLHttpRequest();
				tmp.open("GET", sURI, false);
				tmp.overrideMimeType("text/xml");
				tmp.send(null);
				_sarissa_setReadyState(this, 2);
				this._sarissa_copyDOM(tmp.responseXML);
				_sarissa_setReadyState(this, 3);
			}
			else
				this._sarissa_load(sURI);
		}
		catch (objException)
		{
			this.parseError = -1;
		}
		finally
		{
			_sarissa_loadHandler(this);
		}
		return oDoc;
	}; 
	/** 
     * Extends the Element class to emulate IE's transformNodeToObject
     * @uses Mozilla's XSLTProcessor
     * @argument xslDoc The stylesheet to use (a DOM Document instance)
     * @argument oResult The Document to store the transformation result
     */
	Element.prototype.transformNodeToObject = function(xslDoc, oResult)
	{
		var oDoc = document.implementation.createDocument("", "", null);
		oDoc._sarissa_copyDOM(this);
		oDoc.transformNodeToObject(xslDoc, oResult);
	}
    /** 
     * Extends the Document class to emulate IE's transformNodeToObject
     * @uses Mozilla's XSLTProcessor
     * @argument xslDoc The stylesheet to use (a DOM Document instance)
     * @argument oResult The Document to store the transformation result
     */
	Document.prototype.transformNodeToObject = function(xslDoc, oResult)
	{
		var xsltProcessor = null;
		try
		{
		    xsltProcessor = new XSLTProcessor();
		    if(xsltProcessor.reset)
		    {
                // new nsIXSLTProcessor is available
                xsltProcessor.importStylesheet(xslDoc);
                var newFragment = xsltProcessor.transformToFragment(this, oResult);
                oResult._sarissa_copyDOM(newFragment);
		    }
		    else
		    {
                // only nsIXSLTProcessorObsolete is available
                xsltProcessor.transformDocument(this, xslDoc, oResult, null);
		    }
		}
		catch(e)
		{
			if(xslDoc && oResult)
				throw "Sarissa_TransformNodeToObjectException: Failed to transform document. (original exception: "+e+")";
			else if(!xslDoc)
				throw "Sarissa_TransformNodeToObjectException: No Stylesheet Document was provided. (original exception: "+e+")";
			else if(!oResult)
				throw "Sarissa_TransformNodeToObjectException: No Result Document was provided. (original exception: "+e+")";
			else if(xsltProcessor == null)
                throw "Sarissa_XSLTProcessorNotAvailableException: Could not instantiate an XSLTProcessor object. (original exception: "+e+")";
            else
                throw e;
		}
	};
    /** 
     * Extends the Element class to emulate IE's transformNode
     * @uses Mozilla's XSLTProcessor
     * @argument xslDoc The stylesheet to use (a DOM Document instance)
     * @returns the result of the transformation serialized to an XML String
     */
	Element.prototype.transformNode = function(xslDoc)
	{
		var oDoc = document.implementation.createDocument("", "", null);
		oDoc._sarissa_copyDOM(this);
		return oDoc.transformNode(xslDoc);
	}
    /** 
     * Extends the Document class to emulate IE's transformNode
     * @uses Mozilla's XSLTProcessor
     * @argument xslDoc The stylesheet to use (a DOM Document instance)
     * @returns the result of the transformation serialized to an XML String
     */
	Document.prototype.transformNode = function(xslDoc)
	{
		var out = document.implementation.createDocument("", "", null);
		this.transformNodeToObject(xslDoc, out);
		var str = null;
		try
		{
			var serializer = new XMLSerializer();
			str = serializer.serializeToString(out);
		}
		catch(e)
		{
			throw "Sarissa_TransformNodeException: Failed to serialize result document. (original exception: "+e+")";
		}
		return str;
	};
	/**
     * The item method extends the Array to behave as a NodeList. (To use in XPath related operations)
     * Mozilla actually has implemented NodeList but there's no way AFAIK to create one manually.
     * @argument i the index of the member to return
     * @returns the member corresponding to the given index
     */
	Array.prototype.item = function(i)
	{
		return this[i];
	};
	/**
     * The expr property extends the Array to emulate IE's expr property (Here the Array object is given as the result of
     * selectNodes).
     * @returns the XPath expression passed to selectNodes that resulted in this Array (mimmicking NodeList)
     */
	Array.prototype.expr = "";
	/** dummy, used to accept IE's stuff without throwing errors */
	XMLDocument.prototype.setProperty  = function(x,y){};
	/** 
     * Extends the XMLDocument to emulate IE's selectNodes.
     * @argument sExpr the XPath expression to use
     * @argument contextNode this is for internal use only by the same method when called on Elements
     * @returns the result of the XPath search as an (extended) Array
     */
	XMLDocument.prototype.selectNodes = function(sExpr, contextNode)
	{
		var oResult = this.evaluate(sExpr, 
                                    (contextNode?contextNode:this), 
                                    this.createNSResolver(this.documentElement),
                                    XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
		var nodeList = new Array(oResult.snapshotLength);
		nodeList.expr = sExpr;
		for(i=0;i<nodeList.length;i++)
			nodeList[i] = oResult.snapshotItem(i);
		return nodeList;
	};
    /** 
     * Extends the Element to emulate IE's selectNodes.
     * @argument sExpr the XPath expression to use
     * @returns the result of the XPath search as an (extended) Array
     */
	Element.prototype.selectNodes = function(sExpr)
	{
		var doc = this.ownerDocument;
		if(doc.selectNodes)
			return doc.selectNodes(sExpr, this);
		else
			throw "SarissaXPathOperationException: Method selectNodes is only supported by XML Nodes";
	};
	/** 
     * Extends the XMLDocument to emulate IE's selectSingleNodes.
     * @argument sExpr the XPath expression to use
     * @argument contextNode this is for internal use only by the same method when called on Elements
     * @returns the result of the XPath search as an (extended) Array
     */
	XMLDocument.prototype.selectSingleNode = function(sExpr, contextNode)
	{
		var ctx = contextNode?contextNode:null;
		sExpr += "[1]";
		var nodeList = this.selectNodes(sExpr, ctx);
		if(nodeList.length > 0)
			return nodeList[0];
		else 
			return null;
	};
    /** 
     * Extends the Element to emulate IE's selectNodes.
     * @argument sExpr the XPath expression to use
     * @returns the result of the XPath search as an (extended) Array
     */
	Element.prototype.selectSingleNode = function(sExpr)
	{
		var doc = this.ownerDocument;
		if(doc.selectSingleNode)
			return doc.selectSingleNode(sExpr, this);
		else
			throw "SarissaXPathOperationException: Method selectSingleNode is only supported by XML Nodes. (original exception: "+e+")";
	};
}
else if (_SARISSA_IS_IE)
{
	//============================================
	// Section: IE Initialization
	//============================================
	// Add NodeType constants; missing in IE4, 5 and 6
	if(!window.Node)
	{
		var Node = {
			ELEMENT_NODE: 1,
			ATTRIBUTE_NODE: 2,
			TEXT_NODE: 3,
			CDATA_SECTION_NODE: 4,
			ENTITY_REFERENCE_NODE: 5,
			ENTITY_NODE: 6,
			PROCESSING_INSTRUCTION_NODE: 7,
			COMMENT_NODE: 8,
			DOCUMENT_NODE: 9,
			DOCUMENT_TYPE_NODE: 10,
			DOCUMENT_FRAGMENT_NODE: 11,
			NOTATION_NODE: 12
		}
	}
	// for XSLT parameter names
	_SARISSA_IEPREFIX4XSLPARAM = "xsl:";
	// used to store the most recent ProgID available out of the above
	var _SARISSA_DOM_PROGID = "";
	var _SARISSA_XMLHTTP_PROGID = "";
	/** Called when the Sarissa_xx.js file is parsed, to pick most recent ProgIDs for IE, then gets destroyed */
	function pickRecentProgID(idList)
	{
		// found progID flag
		var bFound = false;
		for (var i=0; i < idList.length && !bFound; i++)
		{
			try
			{
				var oDoc = new ActiveXObject(idList[i]);
				o2Store = idList[i];
				bFound = true;
			}
			catch (objException)
			{
				// trap; try next progID
			}
		}
		if (!bFound)
			throw "Sarissa_Exception: Could not retreive a valid progID of Class: " + idList[idList.length-1]+". (original exception: "+e+")";
		idList = null;
		return o2Store;
	};
	// store proper progIDs
	_SARISSA_DOM_PROGID = pickRecentProgID(["Msxml2.DOMDocument.4.0", "Msxml2.DOMDocument.3.0", "MSXML2.DOMDocument", "MSXML.DOMDocument", "Microsoft.XmlDom"]);
	_SARISSA_XMLHTTP_PROGID = pickRecentProgID(["Msxml2.XMLHTTP.4.0", "MSXML2.XMLHTTP.3.0", "MSXML2.XMLHTTP", "Microsoft.XMLHTTP"]);
	// we dont need this anymore
	pickRecentProgID = null;
	//============================================
	// Section: Factory methods (IE)
	//============================================
	// The mozilla version is documented
	Sarissa.getDomDocument = function(sUri, sName)
	{
		var oDoc = new ActiveXObject(_SARISSA_DOM_PROGID);
		// if a root tag name was provided, we need to load it in the DOM object
		if (sName)
		{
			// if needed, create an artifical namespace prefix the way Moz does
			if (sUri)
			{
				oDoc.loadXML("<a" + _sarissa_iNsCounter + ":" + sName + " xmlns:a" + _sarissa_iNsCounter + "=\"" + sUri + "\" />");
				// don't use the same prefix again
				++_sarissa_iNsCounter;
			}
			else
				oDoc.loadXML("<" + sName + "/>");
		}
		return oDoc;
	};
	// Factory method, returns an IXMLHTTPRequest object 
	// AFAIK, the object behaves exactly like 
	// Mozilla's XmlHttpRequest
	Sarissa.getXmlHttpRequest = function()
	{
		return new ActiveXObject(_SARISSA_XMLHTTP_PROGID);
	};
}
// Factory Class
function Sarissa(){}
// TODO: figure out how to implement support for both Mozilla's and IE's 
// XSL Processor objects to improove performance for reusable stylesheets.
/** 
 * Factory method, used to set xslt parameters.
 * @argument oXslDoc the target XSLT DOM Document
 * @argument sParamName the name of the XSLT parameter
 * @argument sParamValue the value of the XSLT parameter
 * @returns whether the parameter was set succefully
 */
Sarissa.setXslParameter = function(oXslDoc, sParamQName, sParamValue)
{
	try
	{
		var params = oXslDoc.getElementsByTagName(_SARISSA_IEPREFIX4XSLPARAM+"param");
		var iLength = params.length;
		var bFound = false;
		var param;
		
		if(sParamValue)
		{
			for(i=0; i < iLength && !bFound;i++)
			{
				// match a param name attribute with the name given as argument
				if(params[i].getAttribute("name") == sParamQName)
				{
					param = params[i];
					// clean up the parameter
					while(param.firstChild)
						param.removeChild(param.firstChild);
					if(!sParamValue || sParamValue == null)
					{
						// do nothing; we've cleaned up the parameter anyway
					}
					// if String
					else if(typeof sParamValue == "string")
					{ 
						param.setAttribute("select", sParamValue);
						bFound = true;
					}
					// if node
					else if(sParamValue.nodeName)
					{
						param.removeAttribute("select");
						param.appendChild(sParamValue.cloneNode(true));
						bFound = true;
					}
					// if NodeList
					else if (sParamValue.item(0)
						&& sParamValue.item(0).nodeType)
					{
						for(j=0;j < sParamValue.length;j++)
						if(sParamValue.item(j).nodeType) // check if this is a Node
							param.appendChild(sParamValue.item(j).cloneNode(true));
						bFound = true;
					}
					// if Array or IE's IXMLDOMNodeList
					else
						throw "SarissaTypeMissMatchException in method: Sarissa.setXslParameter. (original exception: "+e+")";
				}
			}
		}
		return bFound;
	}
	catch(e)
	{
		throw e;
		return false;
	}
}
// EOF

