/*****************************************************************************
 *
 * Copyright (c) 2003 Epoz Contributors. See CREDITS.txt
 *
 * This software is subject to the provisions of the Zope Public License,
 * Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
 * THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
 * WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
 * FOR A PARTICULAR PURPOSE.
 *
 *****************************************************************************/

// $Id: epozeditor.js,v 1.3 2004/01/21 09:21:13 oaubert Exp $

/*

Some notes about the script:

- Problem with bound event handlers:
    
    When a method on an object is used as an event handler, the method uses 
    its reference to the object it is defined on. The 'this' keyword no longer
    points to the class, but instead refers to the element on which the event
    is bound. To overcome this problem, you can wrap the method in a class that
    holds a reference to the object and have a method on the wrapper that calls
    the input method in the input object's context. This wrapped method can be
    used as the event handler. An example:

    class Foo() {
        this.foo = function() {
            // the method used as an event handler
            // using this here wouldn't work if the method
            // was passed to addEventListener directly
            this.baz();
        };
        this.baz = function() {
            // some method on the same object
        };
    };

    f = new Foo();

    // create the wrapper for the function, args are func, context
    wrapper = new ContextFixer(f.foo, f);

    // the wrapper can be passed to addEventListener, 'this' in the method
    // will be pointing to the right context.
    some_element.addEventListener("click", wrapper.execute, false);

- Problem with window.setTimeout:

    The window.setTimeout function has a couple of problems in usage, all 
    caused by the fact that it expects a *string* argument that will be
    evalled in the global namespace rather than a function reference with
    plain variables as arguments. This makes that the methods on 'this' can
    not be called (the 'this' variable doesn't exist in the global namespace)
    and references to variables in the argument list aren't allowed (since
    they don't exist in the global namespace). To overcome these problems, 
    there's now a singleton instance of a class called Timer, which has one 
    public method called registerFunction. This can be called with a function
    reference and a variable number of extra arguments to pass on to the 
    function.

    Usage:

        timer_instance.registerFunction(this, this.myFunc, 10, 'foo', bar);

        will call this.myFunc('foo', bar); in 10 milliseconds (with 'this'
        as its context).

*/

var validelements = {"BODY":1, "DIV":1, "HEAD":1, "HTML":1, "SPAN":1,
		"TITLE":1, "ABBR":1, "ACRONYM":1, "ADDRESS":1, "BLOCKQUOTE":1, 
		"BR":1, "CITE":1, "CODE":1, "DFN":1, "EM":1, 
		"H1":1, "H2":1, "H3":1, "H4":1, "H5":1, "H6":1, "KBD":1,  
		"P":1, "PRE":1, "Q":1, "SAMP":1, "STRONG":1, "VAR":1, 
		"A":1, "DL":1, "DT":1, "DD":1, "OL":1, "UL":1, "LI":1, 
		"CAPTION":1, "TABLE":1, "TD":1, "TH":1, "TR":1, 
		"COLS":1, "COL":1, "THEAD":1, "TBODY":1,
		"IMG":1, "META":1, "LINK":1, "BASE":1};
                
//----------------------------------------------------------------------------
// Main classes
//----------------------------------------------------------------------------

function Dictionary() {
   this._keys = new Array(0);
   this._values = new Array(0);

   this.None = new Object();

   this.has_key = function(name) {
	for (i = 0 ; i < this._keys.length ; i++) {
	  if (this._keys[i] == name) {
		return true;
	  }
 	}
	return false;
   }

   this.get = function(name) {
	for (i = 0 ; i < this._keys.length ; i++) {
	  if (this._keys[i] == name) {
		return this._values[i];
	  }
 	}
	return this.None;
   }

   this.set = function(name, v) {
	for (i = 0 ; i < this._keys.length ; i++) {
	  if (this._keys[i] == name) {
		this._values[i] = v;
		return;
	  }
 	}
	this._keys.push(name);
	this._values.push(v);
	return;
   }

   this.del = function(name) {
	for (i = 0 ; i < this._keys.length ; i++) {
	  if (this._keys[i] == name) {
		this._keys.splice(i, 1);
		this._values.splice(i, 1);
		return;
	  }
 	}
	return;
   }

   this.keys = function() {
        return this._keys;
   }
  
   this.values = function() {
        return this._values;
   }

   this.update = function(d) {
	for (i = 0 ; i < d._keys.length ; i++) {
		this.set(d._keys[i], d._values[i]);
	}
   }

   this.str = function () {
	var res = "";
	for (i = 0 ; i < this._keys.length ; i++) {
		res = res + "".concat(this._keys[i], " : ", this._values[i], "\n");
	}
	return res;
   }
}

function TALContext(node) {
   this.node = node;

   this.defines = new Dictionary();
   this.attributes = new Dictionary();
   this.repeat = new Dictionary();
   this.content = "";
   this.replace = "";

   this.initialize = function () {
	var currnode = this.editor.getSelectedNode();

	if (! currnode) {
		return;
	}
        function string2dict(foo) {
     	var d = new Dictionary();
 	var l = foo.split(/\s*;\s*/);
     	for (i = 0 ; i < l.length ; i++) {
	   // A regexp would be better, but this does not work correctly:
 	   // s = l[i].match(/^(\w+)\s+(.+)/g);
           var p = l[i].indexOf(" ");
     	   d.set(l[i].substr(0, p), l[i].substr(p+1));
     	};
     	return d;
        };
   
 	if (currnode.getAttribute('tal:attributes')) {
 	    var d = string2dict(currnode.getAttribute('tal:attributes')); 
	    this.attributes.update(d);
	}
	if (currnode.getAttribute('tal:content')) {
	    this.content = currnode.getAttribute('tal:content');
        }
	if (currnode.getAttribute('tal:replace')) {
	    this.replace = currnode.getAttribute('tal:replace');
        }
        while (currnode.tagName) {
	    if (currnode.getAttribute('tal:define')) {
		var d = string2dict(currnode.getAttribute('tal:define'));		
		this.defines.update(d);
	    }
	    if (currnode.getAttribute('tal:repeat')) {
		var d = string2dict(currnode.getAttribute('tal:repeat'));
		this.repeat.update(d);
	    }
            var currnode = currnode.parentNode;
        }
   }

   this.initialize();

   this.str = function() {
        return "TALContext for node " + this.node.parentNode.nodeName.toLowerCase()
		+ "\nContent: " +  this.content + "\nReplace: " + this.replace
		+ "\nAttributes:\n" + this.attributes.str()
 		+ "\nDefines:\n" + this.defines.str()
		+ "\nRepeat:\n" + this.repeat.str() + "\n";
	return res;
   }

}

/* EpozDocument
    
    This essentially wraps the iframe.
    XXX Is this overkill?
    
*/

function EpozDocument(iframe) {
    /* Model */
    
    // attrs
    this.editable = iframe; // the iframe
    this.window = this.editable.contentWindow;
    this.document = this.window.document;
    
    // methods
    this.execCommand = function(command, arg) {
        /* delegate execCommand */
        // XXX Is the command always a string? Can't it be '' or 0 or so?
        if (!arg) arg = null;
        this.document.execCommand(command, false, arg);
    };
    
    this.reloadSource = function() {
        /* reload the source */
        
        // XXX To temporarily work around problems with resetting the
        // state after a reload, currently the whole page is reloaded.
        // XXX Nasty workaround!! to solve refresh problems...
        document.location = document.location;
    };

    this.getDocument = function() {
        /* returns a reference to the window.document object of the iframe */
        return this.document;
    };

    this.getWindow = function() {
        /* returns a reference to the window object of the iframe */
        return this.window;
    };
}

/* EpozEditor

    This controls the document, should be used from the UI.
    
*/

function EpozEditor(document, config, logger) {
    /* Controller */
    
    // attrs
    this.document = document; // the model
    this.config = config; // an object that holds the config values
    this.log = logger; // simple logger object
    this.tools = {}; // mapping id->tool
    
    this._designModeSetAttempts = 0;
    this._initialized = false;

    // some properties to save the selection, required for IE to remember where 
    // in the iframe the selection was
    this._previous_range = null;
    this._saved_selection = null;

    // methods
    this.initialize = function() {
        /* Should be called on iframe.onload, will initialize the editor */
        DOM2Event.initRegistration();
        this._initializeEventHandlers();
        this._setDesignModeWhenReady();
        if (this.getBrowserName() == "IE") {
            this._initialized = true;
        }
        this.getDocument().getWindow().focus();
        this.logMessage('Editor initialized');
    };
    
    this.registerTool = function(id, tool) {
        /* register a tool */
        this.tools[id] = tool;
        tool.initialize(this);
    };

    this.getTool = function(id) {
        /* get a tool by id */
        return this.tools[id];
    };

    this.updateStateHandler = function(event) {
        /* check whether the event is interesting enough to trigger the 
        updateState machinery and act accordingly */
        var interesting_codes = new Array(8, 13, 37, 38, 39, 40, 46);

        if (event.type == 'click' || 
                (event.type == 'keyup' && 
                    interesting_codes.contains(event.keyCode))) {
            // Filthy trick to make the updateState method get called *after*
            // the event has been resolved. This way the updateState methods can
            // react to the situation *after* any actions have been performed (so
            // can actually stay up to date).
            this.updateState(event);
        }
    };
    
    this.updateState = function(event) {
        /* let each tool change state if required */
        // first see if the event is interesting enough to trigger
        // the whole updateState machinery
        var selNode = this.getSelectedNode();
        try {
            for (var id in this.tools) {
                this.tools[id].updateState(selNode, event);
            }
        } catch (e) {
            if (e == UpdateStateCancelBubble) {
                this.updateState(event);
            }
        };
    };
    
    this.saveDocument = function() {
        /* save the document */
        
        // if no dst is available, bail out
        if (!this.config.dst) {
            this.logMessage('No destination URL available!', 2);
            return;
        }
    
        // make sure people can't edit or save during saving
        if (!this._initialized) {
            return;
        }
        this._initialized = false;
        
        // set the window status so people can see we're actually saving
        window.status= "Please wait while saving document...";

        // get the contents from the document
        this.logMessage("Getting HTML from document");
 	var xhtmldoc = Sarissa.getDomDocument();

	// Convert to xhtml, and keep some performance measurements
        this.logMessage("Starting HTML cleanup");
	var start = new Date().getTime();
	var transform = this._convertContentToXHTML(xhtmldoc, 
	                    this.getInnerDocument().documentElement);

	// XXX need to fix this.  Sometimes a spurious "\n\n" text 
	// node appears in the transform, which breaks the Moz 
	// serializer on .xml
        // XXX This is a problem for partial documents!!
// FIXME: Advene fix
// 	var contents =  '<html>' + 
//                         transform.getElementsByTagName("head")[0].xml +
// 	                transform.getElementsByTagName("body")[0].xml +
//                         '</html>';
	var contents = transform.getElementsByTagName("body")[0].xml;
        this.logMessage("Cleanup done, sending document to server");
        var request = Sarissa.getXmlHttpRequest();
    
        function callback (evt) {
            /* callback for Sarissa */
            if (request.readyState == 4) {
                if (request.status != '200' && request.status != '204'){
                    alert('Error saving your data.\nResponse status: ' + 
    		            request.status + 
    		            '.\nCheck your server log for more information.');
                    window.status = "Error saving document"
                } else {
                    if (this.config.reload_after_save) {
                        // XXX Broken!!!
                        /*
                        if (this.getBrowserName() == "Mozilla") {
                            this.getInnerDocument().designMode = "Off";
                        }
                        */
                        this.getDocument().reloadSource();
                        if (this.getBrowserName() == "Mozilla") {
                            this.getInnerDocument().designMode = "On";
                        }
                        /*
                        var selNode = this.getSelectedNode();
                        this.updateState(selNode);
                        */
                    }
                    // we're done so we can start editing again
                    window.status= "Document saved";
                }
                this._initialized = true;
            }
        }
        request.onreadystatechange = (new ContextFixer(callback, 
						       this)).execute;
        request.open("PUT", this.config.dst, true);

        request.setRequestHeader("Content-type", "text/html");
        request.send(contents);

        this.logMessage("Request sent to server");
    
        return;
    };
    
    this.execCommand = function(command, param) {
        /* general stuff like making current selection bold, italics etc. 
            and adding basic elements such as lists
            */
        if (!this._initialized) {
            this.logMessage('Editor not initialized yet!');
            return;
        };
        if (this.getBrowserName() == "IE") {
            this._restoreSelection();
        } else {
            this.getDocument().getWindow().focus();
        };
        this.getDocument().execCommand(command, param);
        var message = 'Command ' + command + ' executed';
        if (param) {
            message += ' with parameter ' + param;
        }
        this.logMessage(message);
    };
    
    this.getSelectedNode = function() {
        /* returns the selected node (read: parent) or none */
        this._restoreSelection();
        var selectednode;
        var browser = this.getBrowserName();
        if (browser == "IE") {
            var sel = this.getInnerDocument().selection;
            var range = sel.createRange();
            selectednode = range.parentElement();
        } else if (browser == "Mozilla") {
            var sel = this.getDocument().window.getSelection();
            selectednode = sel.anchorNode;
        }
        
        return selectednode;
    };
    
    this.getNearestParentOfType = function(node, type) {
        /* well the title says it all ;) */
        // just to be sure...
        this._restoreSelection();
        var type = type.toLowerCase();
        while (node) {
            if (node.nodeName.toLowerCase() == type) {
                return node
            }   
            var node = node.parentNode;
        }
    
        return false;
    };

    this.getDocument = function() {
        /* returns a reference to the document object that wraps the iframe */
        return this.document;
    };

    this.getInnerDocument = function() {
        /* returns a reference to the window.document object of the iframe */
        return this.getDocument().getDocument();
    };

    this.insertNodeAtSelection = function(insertNode) {
        /* insert a newly created node into the document */
        if (!this._initialized) {
            this.logMessage('Editor not initialized yet!');
            return;
        };

        // XXX God, this is long!
        
        var win = this.getDocument().getWindow();
        if (this.getBrowserName() == "IE") {
            this._restoreSelection();
        } else {
            win.focus();
        };
        
        if (_SARISSA_IS_IE) {
            var selection = this.getInnerDocument().selection;
            var html = insertNode.outerHTML;
            var range = selection.createRange();
            try {
                range.pasteHTML(html);        
            } catch (e) {
                // catch error when range is evil for IE
                this.logMessage('Exception in pasting into range: ' + e, 1);
            }
        } else if (_SARISSA_IS_MOZ) {
            // get current selection
            var sel = win.getSelection();

            // get the first range of the selection
            // (there's almost always only one range)
            var range = sel.getRangeAt(0);

            // deselect everything
            sel.removeAllRanges();

            // remove content of current selection from document
            range.deleteContents();

            // get location of current selection
            var container = range.startContainer;
            var pos = range.startOffset;

            // make a new range for the new selection
            var range = this.getInnerDocument().createRange();

            if (container.nodeType == 3 && insertNode.nodeType == 3) {
                // if we insert text in a textnode, do optimized insertion
                container.insertData(pos, insertNode.nodeValue);

                // put cursor after inserted text
                range.setEnd(container, pos+insertNode.length);
                range.setStart(container, pos+insertNode.length);
            } else {
                var afterNode;
                if (container.nodeType == 3) {
                    // when inserting into a textnode
                    // we create 2 new textnodes
                    // and put the insertNode in between

                    var textNode = container;
                    var container = textNode.parentNode;
                    var text = textNode.nodeValue;

                    // text before the split
                    var textBefore = text.substr(0,pos);
                    // text after the split
                    var textAfter = text.substr(pos);

                    var beforeNode = this.getInnerDocument().createTextNode(textBefore);
                    var afterNode = this.getInnerDocument().createTextNode(textAfter);

                    // insert the 3 new nodes before the old one
                    container.insertBefore(afterNode, textNode);
                    container.insertBefore(insertNode, afterNode);
                    container.insertBefore(beforeNode, insertNode);

                    // remove the old node
                    container.removeChild(textNode);
                } else {
                    // else simply insert the node
                    var afterNode = container.childNodes[pos];
                    container.insertBefore(insertNode, afterNode);
                }

                range.setEnd(afterNode, 0);
                range.setStart(afterNode, 0);
            }

            sel.addRange(range);
        } else {
            this.logMessage('Unsupported browser!', 1);
        }
    };

    this.logMessage = function(message, severity) {
        /* log a message using the logger, severity can be 0 (message, default), 1 (warning) or 2 (error) */
        this.log.log(message, severity);
    };
    
    // helper methods
    this.getBrowserName = function() {
        /* returns either 'Mozilla' (for Mozilla, Firebird, Netscape etc.) or 'IE' */
        if (_SARISSA_IS_MOZ) {
            return "Mozilla";
        } else if (_SARISSA_IS_IE) {
            return "IE";
        } else {
            throw "Browser not supported!";
        }
    };
    
    // private methods
    this._initializeEventHandlers = function() {
        /* attache the event handlers to the iframe */
        // Initialize DOM2Event compatibility
        // XXX should come back and change to passing in an element
        this._addEventHandler(this.getInnerDocument(), "click", this.updateStateHandler, this);
        this._addEventHandler(this.getInnerDocument(), "keyup", this.updateStateHandler, this);
        if (this.getBrowserName() == "IE") {
            this._addEventHandler(this.getInnerDocument(), "focus", this._clearSelection, this);
            this._addEventHandler(this.getInnerDocument(), "beforedeactivate", this._saveSelection, this);
            this._addEventHandler(this.getDocument().getWindow(), "blur", this._storeSavedSelection, this);
        };
    };

    this._convertContentToXHTML = function(ownerdoc, htmlnode) {
        /* Given a string of non-well-formed HTML, return a string of 
           well-formed XHTML.
        
           This function works by leveraging the already-excellent HTML 
           parser inside the browser, which generally can turn a pile 
           of crap into a DOM.  We iterate over the HTML DOM, appending 
           new nodes (elements and attributes) into a node.
        
           The primary problems this tries to solve for crappy HTML: mixed 
           element names, elements that open but don't close, 
           and attributes that aren't in quotes.  This can also be adapted 
           to filter out tags that you don't want and clean up inline styles.
        
           Inspired by Guido, adapted by Paul from something in usenet. 
        */

        var i, name, val;

	// Let's filter elements based on those in the 
	// XHTML Basic set at
	// http://www.w3.org/TR/1999/WD-xhtml-basic-19991220
	var nodename = htmlnode.nodeName;
	if (htmlnode.nodeType == 1) {
	    if (nodename == "B") nodename = "STRONG";
	    else if (nodename == "I") nodename = "EM";
	    /*
            else if (!(nodename in validelements)) {
		this.logMessage("rej: " + htmlnode.nodeName, 0);
		return;
	    }
            */
	}
        var xhtmlnode = ownerdoc.createElement(nodename.toLowerCase());
    
        var atts = htmlnode.attributes;
        for (var i = 0; i < atts.length; i++) {
            name = atts[i].nodeName;
            val = atts[i].nodeValue;
            if (!(val == null || val == "" || name == "contentEditable" ||
                  ((name == "rowSpan" || name == "colSpan") && val == 1) )) {
                xhtmlnode.setAttribute(name.toLowerCase(), val);
            }
        } 
    
        var kids = htmlnode.childNodes;
        if (kids.length == 0) {
            if (htmlnode.text && htmlnode.text != "") {
                var text = htmlnode.text;
                var tnode = ownerdoc.createTextNode(text);
                xhtmlnode.appendChild(tnode);
            }
        } else { 
            for (var i = 0; i < kids.length; i++) {
                if (kids[i].nodeType == 1) {
			var newkid = this._convertContentToXHTML(ownerdoc, 
								 kids[i]);
			if (newkid != null) xhtmlnode.appendChild(newkid);
                } else if (kids[i].nodeType == 3) {
                    xhtmlnode.appendChild(ownerdoc.createTextNode(kids[i].nodeValue));
                } else if (kids[i].nodeType == 4) {
            	    xhtmlnode.appendChild(ownerdoc.createCDATASection(kids[i].nodeValue));
                } 
            }
        } 
    
        return xhtmlnode;
    };

    this._setDesignModeWhenReady = function() {
        /* Rather dirty polling loop to see if Mozilla is done doing it's
            initialization thing so design mode can be set.
        */
        this._designModeSetAttempts++;
        if (this._designModeSetAttempts > 25) {
            alert('Couldn\'t set design mode. Epoz will not work on this browser.');
            return;
        };
        if (_SARISSA_IS_IE) {
            return;
        }
        try {
            this._setDesignMode();
        } catch (e) {
            // register a function to the timer_instance because 
            // window.setTimeout can't refer to 'this'...
            timer_instance.registerFunction(this, this._setDesignModeWhenReady, 100);
        }
    };

    this._setDesignMode = function() {
        this.getInnerDocument().designMode = "On";
        this.execCommand("undo");
        // note the negation: the argument doesn't work as expected...
        // XXX Why doesn't this work!?!
        this.execCommand("useCSS", !this.config.use_css);
        this._initialized = true;
    };

    this._addEventHandler = function(element, event, method, context) {
        // XXX Method duplication, which one should survive? Or do we want
        // helper *functions* instead?
        var wrappedmethod = new ContextFixer(method, context);
        if (_SARISSA_IS_MOZ) {
            element.addEventListener(event, wrappedmethod.execute, false);
        } else if (_SARISSA_IS_IE) {
            element.attachEvent("on" + event, wrappedmethod.execute);
        } else {
            throw "Unsupported browser!";
        }
    };

    this._saveSelection = function() {
        /* Save the selection, works around a problem with IE 
        where the selection in the iframe gets lost */
        this._saved_range = this.getInnerDocument().selection.createRange();
    };

    this._storeSavedSelection = function() {
        this._previous_range = this._saved_range;
    };

    this._restoreSelection = function() {
        /* re-selects the previous selection in IE */
        if (this._previous_range) {
            this._previous_range.select();
            this._previous_range = null;
        }
    };

    this._clearSelection = function() {
        /* clear the last stored selection */
        this._previous_range = null;
    };
}

/* EpozUI

    This holds view-specific logic and event handlers
    
*/

// The UI object
function EpozUI(textstyleselectid) {
    /* View */
    
    // attributes
    this.tsselect = document.getElementById(textstyleselectid);

    this.initialize = function(editor) {
        /* initialize the ui like tools */
        this.editor = editor;
    };
    
    // event handlers
    this.basicButtonHandler = function(action) {
        /* event handler for basic actions (toolbar buttons) */
        this.editor.execCommand(action);
        this.editor.updateState();
    };

    this.saveButtonHandler = function() {
        /* handler for the save button */
        this.editor.saveDocument();
    };

    this.setTextStyle = function(style) {
        /* method for the text style pulldown */
        // XXX Yuck!!
        if (this.editor.getBrowserName() == "IE") {
            style = '<' + style + '>';
        };
        this.editor.execCommand('formatblock', style);
    };

    this.updateState = function(selNode) {
        /* set the text-style pulldown */
    
        // first get the nearest style
        var styles = {}; // use an object here so we can use the 'in' operator later on
        for (var i=0; i < this.tsselect.options.length; i++) {
            // XXX we should cache this
            styles[this.tsselect.options[i].value.toUpperCase()] = i;
        }
        
        var currnode = selNode;
        var index = 0;
        while (currnode) {
            if (currnode.nodeName.toUpperCase() in styles) {
                index = styles[currnode.nodeName.toUpperCase()];
                break
            }
            currnode = currnode.parentNode;
        }

        this.tsselect.selectedIndex = index;
    };
}

//----------------------------------------------------------------------------
// Toolboxes
//----------------------------------------------------------------------------

function EpozTool() {
    /* Superclass for tools */

    // methods
    this.initialize = function(editor) {
        /* Initialize the tool.
            Obviously this can be overriden but it will do
            for the most simple cases
        */
        this.editor = editor;
    };
    
    this.updateState = function(selNode, event) {
        /* Is called when user moves cursor to other element.
            Should be overridden for tools that have different
            states (usually an 'add' and 'edit' state).
        */
    };

    // private methods
    this._addEventHandler = function(element, event, method, context) {
        /* method to add an event handler for both IE and Mozilla */
        var wrappedmethod = new ContextFixer(method, context);
        if (_SARISSA_IS_MOZ) {
            element.addEventListener(event, wrappedmethod.execute, false);
        } else if (_SARISSA_IS_IE) {
            element.attachEvent("on" + event, wrappedmethod.execute);
        } else {
            throw "Unsupported browser!";
        }
    };

    this._selectSelectItem = function(select, item) {
        /* select a certain item from a select */
        for (var i=0; i < select.options.length; i++) {
            var option = select.options[i];
            if (option.value == item) {
                select.selectedIndex = i;
                return;
            }
        }
        select.selectedIndex = 0;
    };
}

function ColorchooserTool(fgcolorbuttonid, hlcolorbuttonid, colorchooserid) {
    /* the colorchooser */
    
    this.fgcolorbutton = document.getElementById(fgcolorbuttonid);
    this.hlcolorbutton = document.getElementById(hlcolorbuttonid);
    this.ccwindow = document.getElementById(colorchooserid);
    this.command = null;

    this.initialize = function(editor) {
        /* attach the event handlers */
        this.editor = editor;
        
        this.createColorchooser(this.ccwindow);

        this._addEventHandler(this.fgcolorbutton, "click", this.openFgColorChooser, this);
        this._addEventHandler(this.hlcolorbutton, "click", this.openHlColorChooser, this);
        this._addEventHandler(this.ccwindow, "click", this.chooseColor, this);

        this.hide();

        this.editor.logMessage('Colorchooser tool initialized');
    };

    this.updateState = function(selNode) {
        /* update state of the colorchooser */
        this.hide();
    };

    this.openFgColorChooser = function() {
        /* event handler for opening the colorchooser */
        this.command = "forecolor";
        this.show();
    };

    this.openHlColorChooser = function() {
        /* event handler for closing the colorchooser */
        if (this.editor.getBrowserName() == "IE") {
            this.command = "backcolor";
        } else {
            this.command = "hilitecolor";
        }
        this.show();
    };

    this.chooseColor = function(event) {
        /* event handler for choosing the color */
        var target = _SARISSA_IS_MOZ ? event.target : event.srcElement;
        var cell = this.editor.getNearestParentOfType(target, 'td');
        this.editor.execCommand(this.command, cell.getAttribute('bgColor'));
        this.hide();
    
        this.editor.logMessage('Color chosen');
    };

    this.show = function(command) {
        /* show the colorchooser */
        this.ccwindow.style.display = "block";
    };

    this.hide = function() {
        /* hide the colorchooser */
        this.command = null;
        this.ccwindow.style.display = "none";
    };

    this.createColorchooser = function(table) {
        /* create the colorchooser table */
        
        var chunks = new Array('00', '33', '66', '99', 'CC', 'FF');
        table.setAttribute('id', 'epoz-colorchooser-table');
        table.style.borderWidth = '2px';
        table.style.borderStyle = 'solid';
        table.style.position = 'absolute';
        table.style.cursor = 'default';
        table.style.display = 'none';

        var tbody = document.createElement('tbody');

        for (var i=0; i < 6; i++) {
            var tr = document.createElement('tr');
            var r = chunks[i];
            for (var j=0; j < 6; j++) {
                var g = chunks[j];
                for (var k=0; k < 6; k++) {
                    var b = chunks[k];
                    var color = '#' + r + g + b;
                    var td = document.createElement('td');
                    td.setAttribute('bgColor', color);
                    td.style.backgroundColor = color;
                    td.style.borderWidth = '1px';
                    td.style.borderStyle = 'solid';
                    td.style.fontSize = '1px';
                    td.style.width = '10px';
                    td.style.height = '10px';
                    var text = document.createTextNode('\u00a0');
                    td.appendChild(text);
                    tr.appendChild(td);
                }
            }
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);

        return table;
    };
}

ColorchooserTool.prototype = new EpozTool;

function PropertyTool(titlefieldid, descfieldid) {
    /* The property tool */

    this.titlefield = document.getElementById(titlefieldid);
    this.descfield = document.getElementById(descfieldid);

    this.initialize = function(editor) {
        /* attach the event handlers and set the initial values */
        this.editor = editor;
        this._addEventHandler(this.titlefield, "change", this.updateProperties, this);
        this._addEventHandler(this.descfield, "change", this.updateProperties, this);
        
        // set the fields
        var heads = this.editor.getInnerDocument().getElementsByTagName('head');
        if (!heads[0]) {
            this.editor.logMessage('No head in document!', 1);
        } else {
            var head = heads[0];
            var titles = head.getElementsByTagName('title');
            if (titles.length) {
                this.titlefield.value = titles[0].text;
            }
            var metas = head.getElementsByTagName('meta');
            if (metas.length) {
                for (var i=0; i < metas.length; i++) {
                    var meta = metas[i];
                    if (meta.getAttribute('name') && 
                            meta.getAttribute('name').toLowerCase() == 
                            'description') {
                        this.descfield.value = meta.getAttribute('content');
                        break;
                    }
                }
            }
        }

        this.editor.logMessage('Property tool initialized');
    };

    this.updateProperties = function() {
        /* event handler for updating the properties form */
        var doc = this.editor.getInnerDocument();
        var heads = doc.getElementsByTagName('HEAD');
        if (!heads) {
            this.editor.logMessage('No head in document!', 1);
            return;
        }

        var head = heads[0];

        // set the title
        var titles = head.getElementsByTagName('title');
        if (!titles) {
            var title = doc.createElement('title');
            var text = doc.createTextNode(this.titlefield.value);
            title.appendChild(text);
            head.appendChild(title);
        } else {
            titles[0].childNodes[0].nodeValue = this.titlefield.value;
        }

        // let's just fulfill the usecase, not think about more properties
        // set the description
        var metas = doc.getElementsByTagName('meta');
        var descset = 0;
        for (var i=0; i < metas.length; i++) {
            var meta = metas[i];
            if (meta.getAttribute('name').toLowerCase() == 'description') {
                meta.setAttribute('content', this.descfield.value);
            }
        }

        if (!descset) {
            var meta = doc.createElement('meta');
            meta.setAttribute('name', 'description');
            meta.setAttribute('content', this.descfield.value);
            head.appendChild(meta);
        }

        this.editor.logMessage('Properties modified');
    };
}

PropertyTool.prototype = new EpozTool;

function LinkTool(inputid, buttonid) {
    /* Add and update hyperlinks */
    
    this.input = document.getElementById(inputid);
    this.button = document.getElementById(buttonid);
    
    this.initialize = function(editor) {
        /* attach the event handlers */
        this.editor = editor;
        this._addEventHandler(this.input, "blur", this.updateLink, this);
        this._addEventHandler(this.button, "click", this.addLink, this);

        this.editor.logMessage('Link tool initialized');
    };
    
    this.addLink = function(event) {
        /* add a link */
        var url = this.input.value;
        var currnode = this.editor.getSelectedNode();
        var linkel = this.editor.getNearestParentOfType(currnode, 'a');
        if (!linkel) {
            this.editor.execCommand("CreateLink", url);
        } else {
            linkel.setAttribute('href', url);
        }

        this.editor.logMessage('Link added');
    };
    
    this.updateLink = function() {
        /* update the current link */
        var currnode = this.editor.getSelectedNode();
        var linkel = this.editor.getNearestParentOfType(currnode, 'a');
        if (!linkel) {
            return;
        }

        var url = this.input.value;
        linkel.setAttribute('href', url);

        this.editor.logMessage('Link modified');
    };
    
    this.updateState = function(selNode) {
        /* if we're inside a link, update the input, else empty it */
        var linkel = this.editor.getNearestParentOfType(selNode, 'a');
        if (linkel) {
            this.input.value = linkel.getAttribute('href');
        } else {
            this.input.value = '';
        }
    };
}

LinkTool.prototype = new EpozTool;

function ImageTool(inputfieldid, insertbuttonid) {
    /* Image tool to add images */
    
    this.inputfield = document.getElementById(inputfieldid);
    this.insertbutton = document.getElementById(insertbuttonid);

    this.initialize = function(editor) {
        /* attach the event handlers */
        this.editor = editor;

        this._addEventHandler(this.insertbutton, "click", this.addImage, this);

        this.editor.logMessage('Image tool initialized');
    };

    this.addImage = function() {
        /* add an image */
        var url = this.inputfield.value;
        this.editor.execCommand("InsertImage", url);

        this.editor.logMessage('Image inserted');
    };
}

ImageTool.prototype = new EpozTool;

function TableTool(addtabledivid, edittabledivid, newrowsinputid, 
                    newcolsinputid, makeheaderinputid, classselectid, alignselectid, addtablebuttonid,
                    addrowbuttonid, delrowbuttonid, addcolbuttonid, delcolbuttonid) {
    /* The table tool */

    // XXX There are some awfully long methods in here!!
    

    // a lot of dependencies on html elements here, but most implementations
    // will use them all I guess
    this.addtablediv = document.getElementById(addtabledivid);
    this.edittablediv = document.getElementById(edittabledivid);
    this.newrowsinput = document.getElementById(newrowsinputid);
    this.newcolsinput = document.getElementById(newcolsinputid);
    this.makeheaderinput = document.getElementById(makeheaderinputid);
    this.classselect = document.getElementById(classselectid);
    this.alignselect = document.getElementById(alignselectid);
    this.addtablebutton = document.getElementById(addtablebuttonid);
    this.addrowbutton = document.getElementById(addrowbuttonid);
    this.delrowbutton = document.getElementById(delrowbuttonid);
    this.addcolbutton = document.getElementById(addcolbuttonid);
    this.delcolbutton = document.getElementById(delcolbuttonid);

    // register event handlers
    this.initialize = function(editor) {
        /* attach the event handlers */
        this.editor = editor;
        this._addEventHandler(this.addtablebutton, "click", this.addTable, this);
        this._addEventHandler(this.addrowbutton, "click", this.addTableRow, this);
        this._addEventHandler(this.delrowbutton, "click", this.delTableRow, this);
        this._addEventHandler(this.addcolbutton, "click", this.addTableColumn, this);
        this._addEventHandler(this.delcolbutton, "click", this.delTableColumn, this);
        this._addEventHandler(this.alignselect, "change", this.setColumnAlign, this);
        this._addEventHandler(this.classselect, "change", this.setTableClass, this);
        this.addtablediv.style.display = "block";
        this.edittablediv.style.display = "none";
        this.editor.logMessage('Table tool initialized');
    };

    this.updateState = function(selNode) {
        /* update the state (add/edit) and update the pulldowns (if required) */
        var table = this.editor.getNearestParentOfType(selNode, 'table');
        if (table) {
            this.addtablediv.style.display = "none";
            this.edittablediv.style.display = "block";
            var td = this.editor.getNearestParentOfType(selNode, 'td');
            if (!td) {
                td = this.editor.getNearestParentOfType(selNode, 'th');
            }
            if (td) {
                var align = td.getAttribute('align');
                if (this.editor.config.use_css) {
                    align = td.style.textAlign;
                }
                this._selectSelectItem(this.alignselect, align);
            }
            this._selectSelectItem(this.classselect, table.getAttribute('class'));
        } else {
            this.edittablediv.style.display = "none";
            this.addtablediv.style.display = "block";
            this.alignselect.selectedIndex = 0;
            this.classselect.selectedIndex = 0;
        }
    };

    this.addTable = function() {
        /* add a table */
        var rows = this.newrowsinput.value;
        var cols = this.newcolsinput.value;
        var makeHeader = this.makeheaderinput.checked;
        var classchooser = document.getElementById("epoz-table-classchooser-add");
        var tableclass = this.classselect.options[this.classselect.selectedIndex].value;
        var doc = this.editor.getInnerDocument();

        table = doc.createElement("table");
        table.setAttribute("border", "1");
        table.setAttribute("cellpadding", "8");
        table.setAttribute("cellspacing", "2");
        table.setAttribute("class", tableclass);

        // If the user wants a row of headings, make them
        if (makeHeader) {
            var tr = doc.createElement("tr");
            var thead = doc.createElement("thead");
            for (i=0; i < cols; i++) {
                var th = doc.createElement("th");
                th.appendChild(doc.createTextNode("Col " + i+1));
                tr.appendChild(th);
            }
            thead.appendChild(tr);
            table.appendChild(thead);
        }

        tbody = doc.createElement("tbody");
        for (var i=0; i < rows; i++) {
            var tr = doc.createElement("tr");
            for (var j=0; j < cols; j++) {
                var td = doc.createElement("td");
                var content = doc.createTextNode('\u00a0');
                td.appendChild(content);
                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);
        this.editor.insertNodeAtSelection(table);

        this.editor.logMessage('Table added');
    };

    this.addTableRow = function() {
        /* Find the current row and add a row after it */
        var currnode = this.editor.getSelectedNode();
        var currtbody = this.editor.getNearestParentOfType(currnode, "TBODY");
        var bodytype = "tbody";
        if (!currtbody) {
            currtbody = this.editor.getNearestParentOfType(currnode, "THEAD");
            bodytype = "thead";
        }
        var parentrow = this.editor.getNearestParentOfType(currnode, "TR");
        var nextrow = parentrow.nextSibling;

        // get the number of cells we should place
        var colcount = 0;
        for (var i=0; i < currtbody.childNodes.length; i++) {
            var el = currtbody.childNodes[i];
            if (el.nodeType != 1) {
                continue;
            }
            if (el.nodeName.toLowerCase() == 'tr') {
                var cols = 0;
                for (var j=0; j < el.childNodes.length; j++) {
                    if (el.childNodes[j].nodeType == 1) {
                        cols++;
                    }
                }
                if (cols > colcount) {
                    colcount = cols;
                }
            }
        }

        var newrow = this.editor.getInnerDocument().createElement("TR");

        for (var i = 0; i < colcount; i++) {
            var newcell;
            if (bodytype == 'tbody') {
                newcell = this.editor.getInnerDocument().createElement("TD");
            } else {
                newcell = this.editor.getInnerDocument().createElement("TH");
            }
            var newcellvalue = this.editor.getInnerDocument().createTextNode("\u00a0");
            newcell.appendChild(newcellvalue);
            newrow.appendChild(newcell);
        }

        if (!nextrow) {
            currtbody.appendChild(newrow);
        } else {
            currtbody.insertBefore(newrow, nextrow);
        }
        
        this.editor.logMessage('Table row added');
    };

    this.delTableRow = function() {
        /* Find the current row and delete it */
        var currnode = this.editor.getSelectedNode();
        var parentrow = this.editor.getNearestParentOfType(currnode, "TR");
        if (!parentrow) {
            this.editor.logMessage('No row to delete', 1);
            return;
        }

        // remove the row
        parentrow.parentNode.removeChild(parentrow);

        this.editor.logMessage('Table row removed');
    };

    this.addTableColumn = function() {
        /* Add a new column after the current column */
        var currnode = this.editor.getSelectedNode();
        var currtd = this.editor.getNearestParentOfType(currnode, 'TD');
        if (!currtd) {
            currtd = this.editor.getNearestParentOfType(currnode, 'TH');
        }
        if (!currtd) {
            this.editor.logMessage('No parentcolumn found!', 1);
            return;
        }
        var currtr = this.editor.getNearestParentOfType(currnode, 'TR');
        var currtable = this.editor.getNearestParentOfType(currnode, 'TABLE');
        
        // get the current index
        var tdindex = this._getColIndex(currtd);
        this.editor.logMessage('tdindex: ' + tdindex);

        // now add a column to all rows
        // first the thead
        var theads = currtable.getElementsByTagName('THEAD');
        if (theads) {
            for (var i=0; i < theads.length; i++) {
                // let's assume table heads only have ths
                var currthead = theads[i];
                for (var j=0; j < currthead.childNodes.length; j++) {
                    var tr = currthead.childNodes[j];
                    if (tr.nodeType != 1) {
                        continue;
                    }
                    var currindex = 0;
                    for (var k=0; k < tr.childNodes.length; k++) {
                        var th = tr.childNodes[k];
                        if (th.nodeType != 1) {
                            continue;
                        }
                        if (currindex == tdindex) {
                            var doc = this.editor.getInnerDocument();
                            var newth = doc.createElement('th');
                            var text = doc.createTextNode('\u00a0');
                            newth.appendChild(text);
                            if (tr.childNodes.length == k+1) {
                                // the column will be on the end of the row
                                tr.appendChild(newth);
                            } else {
                                tr.insertBefore(newth, tr.childNodes[k + 1]);
                            }
                            break;
                        }
                        currindex++;
                    }
                }
            }
        }

        // then the tbody
        var tbodies = currtable.getElementsByTagName('TBODY');
        if (tbodies) {
            for (var i=0; i < tbodies.length; i++) {
                // let's assume table heads only have ths
                var currtbody = tbodies[i];
                for (var j=0; j < currtbody.childNodes.length; j++) {
                    var tr = currtbody.childNodes[j];
                    if (tr.nodeType != 1) {
                        continue;
                    }
                    var currindex = 0;
                    for (var k=0; k < tr.childNodes.length; k++) {
                        var td = tr.childNodes[k];
                        if (td.nodeType != 1) {
                            continue;
                        }
                        if (currindex == tdindex) {
                            var doc = this.editor.getInnerDocument();
                            var newtd = doc.createElement('td');
                            var text = doc.createTextNode('\u00a0');
                            newtd.appendChild(text);
                            if (tr.childNodes.length == k+1) {
                                // the column will be on the end of the row
                                tr.appendChild(newtd);
                            } else {
                                tr.insertBefore(newtd, tr.childNodes[k + 1]);
                            }
                            break;
                        }
                        currindex++;
                    }
                }
            }
        }
        this.editor.logMessage('Table column added');
    };

    this.delTableColumn = function() {
        /* remove a column */
        var currnode = this.editor.getSelectedNode();
        var currtd = this.editor.getNearestParentOfType(currnode, 'TD');
        if (!currtd) {
            currtd = this.editor.getNearestParentOfType(currnode, 'TH');
        }
        var currcolindex = this._getColIndex(currtd);
        var currtable = this.editor.getNearestParentOfType(currnode, 'TABLE');

        // remove the theaders
        var heads = currtable.getElementsByTagName('THEAD');
        if (heads.length) {
            for (var i=0; i < heads.length; i++) {
                var thead = heads[i];
                for (var j=0; j < thead.childNodes.length; j++) {
                    var tr = thead.childNodes[j];
                    if (tr.nodeType != 1) {
                        continue;
                    }
                    var currindex = 0;
                    for (var k=0; k < tr.childNodes.length; k++) {
                        var th = tr.childNodes[k];
                        if (th.nodeType != 1) {
                            continue;
                        }
                        if (currindex == currcolindex) {
                            tr.removeChild(th);
                            break;
                        }
                        currindex++;
                    }
                }
            }
        }

        // now we remove the column field, a bit harder since we need to take 
        // colspan and rowspan into account XXX Not right, fix theads as well
        var bodies = currtable.getElementsByTagName('TBODY');
        for (var i=0; i < bodies.length; i++) {
            var currtbody = bodies[i];
            var relevant_rowspan = 0;
            for (var j=0; j < currtbody.childNodes.length; j++) {
                var tr = currtbody.childNodes[j];
                if (tr.nodeType != 1) {
                    continue;
                }
                var currindex = 0
                for (var k=0; k < tr.childNodes.length; k++) {
                    var cell = tr.childNodes[k];
                    if (cell.nodeType != 1) {
                        continue;
                    }
                    var colspan = cell.getAttribute('colspan');
                    if (currindex == currcolindex) {
                        tr.removeChild(cell);
                        break;
                    }
                    currindex++;
                }
            }
        }
        this.editor.logMessage('Table column deleted');
    };

    this.setColumnAlign = function() {
        /* In tables, grab the col element and change its align attr/style */
        var newalign = this.alignselect.options[this.alignselect.selectedIndex].value;

        var currnode = this.editor.getSelectedNode();
        var currtd = this.editor.getNearestParentOfType(currnode, "TD");
        var bodytype = 'tbody';
        if (!currtd) {
            currtd = this.editor.getNearestParentOfType(currnode, "TH");
            bodytype = 'thead';
        }
        var currcolindex = this._getColIndex(currtd);
        var currtable = this.editor.getNearestParentOfType(currnode, "TABLE");

        // unfortunately this is not enough to make the browsers display
        // the align, we need to set it on individual cells as well and
        // mind the rowspan...
        for (var i=0; i < currtable.childNodes.length; i++) {
            var currtbody = currtable.childNodes[i];
            if (currtbody.nodeType != 1 || 
                    (currtbody.nodeName.toUpperCase() != "THEAD" &&
                        currtbody.nodeName.toUpperCase() != "TBODY")) {
                continue;
            }
            for (var j=0; j < currtbody.childNodes.length; j++) {
                var row = currtbody.childNodes[j];
                if (row.nodeType != 1) {
                    continue;
                }
                var index = 0;
                for (var k=0; k < row.childNodes.length; k++) {
                    var cell = row.childNodes[k];
                    if (cell.nodeType != 1) {
                        continue;
                    }
                    if (index == currcolindex) {
                        if (this.editor.config.use_css) {
                            cell.style.textAlign = newalign;
                        } else {
                            cell.setAttribute('align', newalign);
                        }
                    }
                    index++;
                }
            }
        }
    };

    this.setTableClass = function() {
        /* set the class for the table */
        var currnode = this.editor.getSelectedNode();
        var currtable = this.editor.getNearestParentOfType(currnode, 'TABLE');

        if (currtable) {
            var sel_class = this.classselect.options[this.classselect.selectedIndex].value;
            if (sel_class) {
                currtable.setAttribute('class', sel_class);
            }
        }
    };

    this._getColIndex = function(currcell) {
        /* Given a node, return an integer for which column it is */
        var prevsib = currcell.previousSibling;
        var currcolindex = 0;
        while (prevsib) {
            if (prevsib.nodeType == 1 && 
                    (prevsib.tagName.toUpperCase() == "TD" || 
                        prevsib.tagName.toUpperCase() == "TH")) {
                var colspan = prevsib.getAttribute('colspan');
                if (colspan) {
                    currcolindex += parseInt(colspan);
                } else {
                    currcolindex++;
                }
            }
            prevsib = prevsib.previousSibling;
            if (currcolindex > 30) {
                alert("Recursion detected when counting column position");
                return;
            }
        }

        return currcolindex;
    };
}

TableTool.prototype = new EpozTool;

function ListTool(addulbuttonid, addolbuttonid, ulstyleselectid, olstyleselectid) {
    /* tool to set list styles */

    this.addulbutton = document.getElementById(addulbuttonid);
    this.addolbutton = document.getElementById(addolbuttonid);
    this.ulselect = document.getElementById(ulstyleselectid);
    this.olselect = document.getElementById(olstyleselectid);

    this.style_to_type = {'decimal': '1',
                            'lower-alpha': 'a',
                            'upper-alpha': 'A',
                            'lower-roman': 'i',
                            'upper-roman': 'I',
                            'disc': 'disc',
                            'square': 'square',
                            'circle': 'circle',
                            'none': 'none'
                            };
    this.type_to_style = {'1': 'decimal',
                            'a': 'lower-alpha',
                            'A': 'upper-alpha',
                            'i': 'lower-roman',
                            'I': 'upper-roman',
                            'disc': 'disc',
                            'square': 'square',
                            'circle': 'circle',
                            'none': 'none'
                            };
    
    this.initialize = function(editor) {
        /* attach event handlers */
        this.editor = editor;

        this._addEventHandler(this.addulbutton, "click", this.addUnorderedList, this);
        this._addEventHandler(this.addolbutton, "click", this.addOrderedList, this);
        this._addEventHandler(this.ulselect, "change", this.setUnorderedListStyle, this);
        this._addEventHandler(this.olselect, "change", this.setOrderedListStyle, this);
        this.ulselect.style.display = "none";
        this.olselect.style.display = "none";

        this.editor.logMessage('List style tool initialized');
    };

    this.updateState = function(selNode) {
        /* update the visibility and selection of the list type pulldowns */
        // we're going to walk through the tree manually since we want to 
        // check on 2 items at the same time
        var currnode = selNode;
        while (currnode) {
            if (currnode.nodeName.toLowerCase() == 'ul') {
                if (this.editor.config.use_css) {
                    var currstyle = currnode.style.listStyleType;
                } else {
                    var currstyle = this.type_to_style[currnode.getAttribute('type')];
                }
                this._selectSelectItem(this.ulselect, currstyle);
                this.olselect.style.display = "none";
                this.ulselect.style.display = "inline";
                return;
            } else if (currnode.nodeName.toLowerCase() == 'ol') {
                if (this.editor.config.use_css) {
                    var currstyle = currnode.listStyleType;
                } else {
                    var currstyle = this.type_to_style[currnode.getAttribute('type')];
                }
                this._selectSelectItem(this.olselect, currstyle);
                this.ulselect.style.display = "none";
                this.olselect.style.display = "inline";
                return;
            }

            currnode = currnode.parentNode;
            this.ulselect.selectedIndex = 0;
            this.olselect.selectedIndex = 0;
        }

        this.ulselect.style.display = "none";
        this.olselect.style.display = "none";
    };

    this.addUnorderedList = function() {
        /* add an unordered list */
        this.ulselect.style.display = "inline";
        this.olselect.style.display = "none";
        this.editor.execCommand("insertunorderedlist");
    };

    this.addOrderedList = function() {
        /* add an ordered list */
        this.olselect.style.display = "inline";
        this.ulselect.style.display = "none";
        this.editor.execCommand("insertorderedlist");
    };

    this.setUnorderedListStyle = function() {
        /* set the type of an ul */
        var currnode = this.editor.getSelectedNode();
        var ul = this.editor.getNearestParentOfType(currnode, 'ul');
        var style = this.ulselect.options[this.ulselect.selectedIndex].value;
        if (this.editor.config.use_css) {
            ul.style.listStyleType = style;
        } else {
            ul.setAttribute('type', this.style_to_type[style]);
        }

        this.editor.logMessage('List style changed');
    };

    this.setOrderedListStyle = function() {
        /* set the type of an ol */
        var currnode = this.editor.getSelectedNode();
        var ol = this.editor.getNearestParentOfType(currnode, 'ol');
        var style = this.olselect.options[this.olselect.selectedIndex].value;
        if (this.editor.config.use_css) {
            ol.style.listStyleType = style;
        } else {
            ol.setAttribute('type', this.style_to_type[style]);
        }

        this.editor.logMessage('List style changed');
    };
}

ListTool.prototype = new EpozTool;

function ShowPathTool() {
    /* shows the path to the current element in the status bar */

    this.updateState = function(selNode) {
        /* calculate and display the path */
        var path = '';
        var currnode = selNode;
        while (currnode.nodeName != '#document') {
            path = '/' + currnode.nodeName.toLowerCase() + path;
            currnode = currnode.parentNode;
        }
        
        window.status = path;
    };
}

ShowPathTool.prototype = new EpozTool;

function ShowTALTool(talnodeid, talattributesid, talcontentid, talreplaceid, talrepeatid, taldefineid) {
    /* shows the TAL attributes of the current element */
    
    this.tal_node = document.getElementById(talnodeid);
    this.tal_attributes = document.getElementById(talattributesid);
    this.tal_content = document.getElementById(talcontentid);
    this.tal_replace = document.getElementById(talreplaceid);
    this.tal_repeat = document.getElementById(talrepeatid);
    this.tal_define = document.getElementById(taldefineid);
    
    this.initialize = function(editor) {
        /* attach event handlers */
        this.editor = editor;

        this._addEventHandler(this.tal_replace, "change", this.update_replace, this);

        this.editor.logMessage('TAL tool initialized - yep');
    };

    this.update_replace = function() {
        /* update the current link */
        var currnode = this.editor.getSelectedNode().parentNode;
        var url = this.tal_replace.value;
	url.replace('http://.+/packages/\w+/', 'here/');
	this.tal_replace.value = url;
        this.editor.logMessage('Update replace value');
    };

    this.updateState = function(selNode) {
	var currnode = selNode.parentNode;
	this.tal_node.value = currnode.nodeName.toLowerCase();

	var c = new TALContext(selNode);

	//	this.editor.logMessage(c.str());
	this.tal_content.value = c.content;
	this.tal_replace.value = c.replace;
	this.tal_attributes.value = c.attributes.str();
	this.tal_repeat.value = c.repeat.str();
	this.tal_define.value = c.defines.str();
    };
}

ShowTALTool.prototype = new EpozTool;

//----------------------------------------------------------------------------
// Loggers
//----------------------------------------------------------------------------

function DebugLogger() {
    /* Alert all messages */
    
    this.log = function(message, severity) {
        /* log a message */
        if (severity > 1) {
            alert("Error: " + message);
        } else if (severity == 1) {
            alert("Warning: " + message);
        } else {
            alert("Log message: " + message);
        }
    };
}

function PlainLogger(debugelid, maxlength) {
    /* writes messages to a debug tool and throws errors */

    this.debugel = document.getElementById(debugelid);
    this.maxlength = maxlength;
    
    this.log = function(message, severity) {
        /* log a message */
        if (severity > 1) {
            throw message;
        } else {
            if (this.maxlength) {
                if (this.debugel.childNodes.length > this.maxlength - 1) {
                    this.debugel.removeChild(this.debugel.childNodes[0]);
                }
            }
            var now = new Date();
            var time = now.getHours() + ':' + now.getMinutes() + ':' + now.getSeconds();
            
            var div = document.createElement('div');
            var text = document.createTextNode(time + ' - ' + message);
            div.appendChild(text);
            this.debugel.appendChild(div);
        }
    };
}

//----------------------------------------------------------------------------
// Helper classes
//----------------------------------------------------------------------------

/* ContextFixer, fixes a problem with the prototype based model

    When a method is called in certain particular ways, for instance
    when it is used as an event handler, the context for the method
    is changed, so 'this' inside the method doesn't refer to the object
    on which the method is defined (or to which it is attached), but for
    instance to the element on which the method was bound to as an event
    handler. This class can be used to wrap such a method, the wrapper 
    has one method that can be used as the event handler instead. The
    constructor expects at least 2 arguments, first is a reference to the
    method, second the context (a reference to the object) and optionally
    it can cope with extra arguments, they will be passed to the method
    as arguments when it is called (which is a nice bonus of using 
    this wrapper).
*/

function ContextFixer(func, context) {
    /* Make sure 'this' inside a method points to its class */
    this.func = func;
    this.context = context;
    this.args = arguments;
    var self = this;
    
    this.execute = function() {
        /* execute the method */
        var args = new Array();
        // the first arguments will be the extra ones of the class
        for (var i=0; i < self.args.length - 2; i++) {
            args.push(self.args[i + 2]);
        };
        // the last are the ones passed on to the execute method
        for (var i=0; i < arguments.length; i++) {
            args.push(arguments[i]);
        };
        self.func.apply(self.context, args);
    };
};

/* Alternative implementation of window.setTimeout

    This is a singleton class, the name of the single instance of the
    object is 'timer_instance', which has one public method called
    registerFunction. This method takes at least 2 arguments: a
    reference to the function (or method) to be called and the timeout.
    Arguments to the function are optional arguments to the 
    registerFunction method. Example:

    timer_instance.registerMethod(foo, 100, 'bar', 'baz');

    will call the function 'foo' with the arguments 'bar' and 'baz' with
    a timeout of 100 milliseconds.

    Since the method doesn't expect a string but a reference to a function
    and since it can handle arguments that are resolved within the current
    namespace rather then in the global namespace, the method can be used
    to call methods on objects from within the object (so this.foo calls
    this.foo instead of failing to find this inside the global namespace)
    and since the arguments aren't strings which are resolved in the global
    namespace the arguments work as expected even inside objects.

*/

function Timer() {
    /* class that has a method to replace window.setTimeout */
    this.lastid = 0;
    this.functions = {};
    
    this.registerFunction = function(object, func, timeout) {
        /* register a function to be called with a timeout

            args: 
                func - the function
                timeout - timeout in millisecs
                
            all other args will be passed 1:1 to the function when called
        */
        var args = new Array();
        for (var i=0; i < arguments.length - 3; i++) {
            args.push(arguments[i + 3]);
        }
        var id = this._createUniqueId();
        this.functions[id] = new Array(object, func, args);
        setTimeout("timer_instance._handleFunction(" + id + ")", timeout);
    };

    this._handleFunction = function(id) {
        /* private method that does the actual function call */
        var obj = this.functions[id][0];
        var func = this.functions[id][1];
        var args = this.functions[id][2];
        this.functions[id] = null;
        func.apply(obj, args);
    };

    this._createUniqueId = function() {
        /* create a unique id to store the function by */
        while (this.lastid in this.functions && this.functions[this.lastid]) {
            this.lastid++;
            if (this.lastid > 100000) {
                this.lastid = 0;
            }
        }
        return this.lastid;
    };
};

// create a timer instance in the global namespace, obviously this does some
// polluting but I guess it's impossible to avoid...

// OBVIOUSLY THIS VARIABLE SHOULD NEVER BE OVERWRITTEN!!!
timer_instance = new Timer();

// helper function on the Array object to test for containment
Array.prototype.contains = function(element) {
    /* see if some value is in this */
    for (var i=0; i < this.length; i++) {
        if (element == this[i]) {
            return true;
        };
    };
    return false;
};

// XXX don't know if this is the regular way to define exceptions in JavaScript?
function Exception() {
    return;
};

// throw this as an exception inside an updateState handler to restart the
// update, may be required in situations where updateState changes the structure
// of the document (e.g. does a cleanup or so)
UpdateStateCancelBubble = new Exception();

//----------------------------------------------------------------------------
// Sample
//----------------------------------------------------------------------------

function initEpoz(iframe) {
    /* Although this is meant to be a sample implementation, it can
        be used out-of-the box to run the sample pagetemplate or for simple
        implementations that just don't use some elements. When you want
        to do some customization, this should probably be overridden. For 
        larger customization actions you will have to subclass or roll your 
        own UI object.
    */

    // first we create a logger
    var l = new PlainLogger('epoz-toolbox-debuglog', 5);
    
    // now some config values
    // XXX To mimic the 'old' behaviour, vars should be retrieved from the 
    // iframe (attributes)
    var src = iframe.getAttribute('src');
    var dst = iframe.getAttribute('dst');
    if (!dst) {
        dst = '..';
    }
    var use_css = (iframe.getAttribute('usecss') != "0");
    var reload_src = (iframe.getAttribute('reloadsrc') == "1");
    var conf = {'src': src,
                'dst': dst,
                'use_css': use_css,
                'reload_after_save': reload_src
                };
    
    // the we create the document, hand it over the id of the iframe
    var doc = new EpozDocument(iframe);
    
    // now we can create the controller
    var epoz = new EpozEditor(doc, conf, l);
    
    // add some tools
    // XXX would it be better to pass along elements instead of ids?
    var colorchoosertool = new ColorchooserTool('epoz-forecolor', 'epoz-hilitecolor', 'epoz-colorchooser');
    epoz.registerTool('colorchooser', colorchoosertool);

    var listtool = new ListTool('epoz-list-ul-addbutton', 'epoz-list-ol-addbutton', 'epoz-ulstyles', 'epoz-olstyles');
    epoz.registerTool('listtool', listtool);
    
    var proptool = new PropertyTool('epoz-properties-title', 'epoz-properties-description');
    epoz.registerTool('proptool', proptool);

    var linktool = new LinkTool("epoz-link-input", "epoz-link-button");
    epoz.registerTool('linktool', linktool);

    var imagetool = new ImageTool('epoz-image-input', 'epoz-image-addbutton');
    epoz.registerTool('imagetool', imagetool);

    var tabletool = new TableTool('epoz-toolbox-addtable', 
        'epoz-toolbox-edittable', 'epoz-table-newrows', 'epoz-table-newcols',
        'epoz-table-makeheader', 'epoz-table-classchooser', 'epoz-table-alignchooser',
        'epoz-table-addtable-button', 'epoz-table-addrow-button', 'epoz-table-delrow-button', 'epoz-table-addcolumn-button',
        'epoz-table-delcolumn-button'
        );
    epoz.registerTool('tabletool', tabletool);

    var showpathtool = new ShowPathTool();
    epoz.registerTool('showpathtool', showpathtool);

    var showtaltool = new ShowTALTool('epoz-node-name',
 				      'epoz-attributes-input', 'epoz-content-input',	
				      'epoz-replace-input', 'epoz-repeat-input',
                                      'epoz-define-input');
    epoz.registerTool('showtaltool', showtaltool);
    
    // now we can create a UI object which we can use from the UI
    var ui = new EpozUI('epoz-tb-styles');

    // the ui must be registered to the editor as well so it can be notified
    // of state changes
    epoz.registerTool('ui', ui); // XXX Should this be a different method?

    epoz.node = epoz.document.document.firstChild.childNodes[1].childNodes[8].childNodes[1];
    return epoz;
}
