// DOM2 Events  v2.0
// http://www.dithered.com/javascript/dom2_events/index.html
// code by Chris Nott (chris@NOSPAMdithered.com - remove NOSPAM)
// addWindowEventListener() and removeWindowEventListener() by Andrew Tetlaw

function DOM2Event(DOMEvent, windowEvent, functionArray) {

	// store browser's event object as a property of synthetic event object
   if (windowEvent != null) {
      this._event = windowEvent;
   }
   else if (DOMEvent != null) {
      this._event = DOMEvent;
   }

   if (functionArray && functionArray != window && functionArray.element) var element = functionArray.element;
   
	// add properties
	// Event interface properties
	this.type = this._event.type;
	this.currentTarget = (this._event.currentTarget != null) ? this._event.currentTarget : element;
	this.target = (this._event.target != null) ? this._event.target : (this._event.srcElement != null) ? this._event.srcElement : (element == window && this._event.type == 'load') ? document : null;
	this.eventPhase = (this._event.eventPhase != null) ? this._event.eventPhase : (this.target == this.currentTarget) ? this.AT_TARGET : this.BUBBLING_PHASE;
	this.timeStamp = new Date();  // discard buggy Mozilla timeStamp
	this.bubbles = (this._event.bubbles !== null) ? this._event.bubbles : (this.type == 'blur' || this.type == 'focus' || this.type == 'load' || this.type == 'unload') ? false : true;
	this.cancelable = (this._event.cancelable !== null) ? this._event.cancelable : (this.type == 'click' || this.type == 'mousedown' || this.type == 'mouseout' || this.type == 'mouseover' || this.type == 'mouseup' || this.type == 'submit') ? true : false;
	
	// UIEvent interface properties
	this.view = (this._event.view != null) ? this._event.view : window;
	this.detail = (this._event.detail !== null) ? this._event.detail : (this.type == 'click') ? 1 : (this.type = 'dblclick') ? 2 : 0;
	
	// MouseEvent interface properties
	this.button = DOM2Event._getButton(this._event.button);
	this.altKey = (this._event.altKey !== null) ? this._event.altKey : false;
	this.ctrlKey = (this._event.ctrlKey !== null) ? this._event.ctrlKey : false;
	this.metaKey = (this._event.metaKey !== null) ? this._event.metaKey : false;
	this.shiftKey = (this._event.shiftKey !== null) ? this._event.shiftKey : false;
	this.clientX = DOM2Event._getClientX(this._event.clientX);
	this.clientY = DOM2Event._getClientY(this._event.clientY);
	this.screenX = (this._event.screenX !== null) ? this._event.screenX : 0;
	this.screenY = (this._event.screenY !== null) ? this._event.screenY : 0;
	this.relatedTarget = (this._event.relatedTarget != null) ? this._event.relatedTarget : (this.type == 'mouseover' && this._event.fromElement != null) ? this._event.fromElement : (this.type == 'mouseout' && this._event.toElement != null) ? this._event.toElement : null;
	
	// useful extensions
	this.pageX = DOM2Event._getPageX(this._event.pageX, this._event.clientX);
	this.pageY = DOM2Event._getPageY(this._event.pageY, this._event.clientY);
	this.keyCode = (this._event.keyCode) ? this._event.keyCode : null;
}

DOM2Event.prototype.stopPropagation = function() {
	if (this._event.stopPropagaion != null) {
		this._event.stopPropagaion();
	}
	else if (this._event.cancelBubble !== null) {
		this._event.cancelBubble = true;
	}
};

DOM2Event.prototype.preventDefault = function() {
	if (this._event.preventDefault != null) {
		this._event.preventDefault();
	}
	else if (this._event.returnValue !== null) {
		this._event.returnValue = false;
	}
};
	
// event phase constants 
if (Event == null) {
	var Event = {	
		CAPTURING_PHASE : 1,
		AT_TARGET : 2,
		BUBBLING_PHASE : 3
	};
}


/*****************************************************************************
   Enable DOM2 event listener registration
 *****************************************************************************/
 
// add attachEventListener() and removeEventListener() to elements
DOM2Event.initRegistration = function(element) {
   if (element != null) {
      if (!element.addEventListener) {
   		element.addEventListener = (element == window) ? DOM2Event.addWindowEventListener : DOM2Event.addEventListener;
   		element.removeEventListener = (element == window) ? DOM2Event.removeWindowEventListener : DOM2Event.removeEventListener;
   	}
   }
   else if (!document.addEventListener && (document.all || document.getElementsByTagName)) {				
		window.addEventListener = DOM2Event.addWindowEventListener;
		window.removeEventListener = DOM2Event.removeWindowEventListener;

		var allTags = new Array();
      
      // for IE4+, Op6
      if (document.all) {
         allTags = document.all;
      }
      
      // for Op5
      else if (document.getElementsByTagName) {
         allTags = document.getElementsByTagName('*');
      }
      
      for (element in allTags) {
         if (typeof element != 'object') {
   	      allTags[element].addEventListener = DOM2Event.addEventListener;
	   	   allTags[element].removeEventListener = DOM2Event.removeEventListener;
		   }
      }
	}
};


/*****************************************************************************
   Event listener registration functions 
 *****************************************************************************/
 
// mimic event listeners by maintaining a list of event listener functions that are called thru a DOM0 event handler
// add an event listener to the list
DOM2Event.addEventListener = function(eventType, eventListener) {
	if (!this['on' + eventType]) {
		this['on' + eventType] = function(e) {
			if (!e) e = event;
			var functionArray = eval('this.' + e.type + 'Handler');
         for (var index = 0; index < functionArray.length; index++) {
				if (functionArray[index] != null) {
					functionArray[index](e);
				}
			}
		};
		this[eventType + 'Handler'] = new Array();
		this[eventType + 'Handler'].element = this;
	}
	var index = 0;
	while (this[eventType + 'Handler'][index] != null) {
		index++;
	}
	this[eventType + 'Handler'][index] = eventListener;
};

// remove an event listener from the list
DOM2Event.removeEventListener = function(eventType, eventListener) {
	var functionArray = this[eventType + 'Handler'];
	for (var index = 0; index < functionArray.length; index++) {
		if (functionArray[index] == eventListener) {
			functionArray[index] = null;
		}
	}
};

// in IE, window and this aren't completely identical
// to store the event function, need to explicitly use window instead of this
DOM2Event.addWindowEventListener = function(eventType, eventListener) {
	if (!window['on' + eventType]) {
		window['on' + eventType] = function(e) {
			if (!e) e = event;
			var functionArray = eval('window.' + e.type + 'Handler');
         for (var index = 0; index < functionArray.length; index++) {
				if (functionArray[index] != null) {
					functionArray[index](e);
				}
			}
		};
		window[eventType + 'Handler'] = new Array();
		window[eventType + 'Handler'].element = window;
	}
	var index = 0;
	while (window[eventType + 'Handler'][index] != null) {
		index++;
	}
	window[eventType + 'Handler'][index] = eventListener;
};

// remove an event listener from the list
DOM2Event.removeWindowEventListener = function(eventType, eventListener) {
	var functionArray = window[eventType + 'Handler'];
	for (var index = 0; index < functionArray.length; index++) {
		if (functionArray[index] == eventListener) {
			functionArray[index] = null;
		}
	}
};

/*****************************************************************************
   Methods to fix DOM2 implementations 
 *****************************************************************************/
 
// returns correct button number: left - 0, center - 1, right - 2
DOM2Event._getButton = function(currentButton) {
   if (currentButton != null) {
      var ua = navigator.userAgent.toLowerCase(); 
      var isGecko = (ua.indexOf('gecko') != -1);
	   var isNS60x = (isGecko && ua.indexOf('netscape') != -1 && parseFloat(navigator.appVersion) == 6);
	   
      // in NS6.0x and Opera, button numbers are: left - 1, center - 2, right - 3
      if (isNS60x || ua.indexOf('opera') != -1) {
         return currentButton - 1;
      }
      
      // in IE4+, Koqueror and Safari, button numbers are: left - 1, center - 4, right - 2 but can be combined
      // return button with highest number
      else if (ua.indexOf('msie') != -1 || ua.indexOf('konqueror') != -1 || ua.indexOf('safari') != -1) {
         return (currentButton >= 4) ? 1 : ( (currentButton >= 2) ? 2 : 0);
	   }
		
		// in NS6.1+ and Mozilla, button numbers are ok
      else if (isGecko) {
			return currentButton;
		}
   }
   return null;
};

// returns the distance from window left to event left
DOM2Event._getClientX = function(currentClientX) {
	var ua = navigator.userAgent.toLowerCase(); 
   
   // in Konqueror, Opera and iCab, clientX really contains the pageX value
   if (ua.indexOf('konqueror') != -1 || ua.indexOf('safari') != -1 || ua.indexOf('opera') != -1 || ua.indexOf('icab') != -1) {
      if (document.body && document.body.scrollLeft != null) {
         return currentClientX - document.body.scrollLeft;
      }
      return currentClientX;
   }
   
   // in IE and NS, a good clientX exists
   else if (currentClientX) {
      return currentClientX;
   }
   
   else {
      return null;
   }
};

// returns the distance from window top to event top
DOM2Event._getClientY = function(currentClientY) {
	var ua = navigator.userAgent.toLowerCase(); 

   // in Konqueror, Opera and iCab, clientY really contains the pageY value
   if (ua.indexOf('konqueror') != -1 || ua.indexOf('safari') != -1 || ua.indexOf('opera') != -1 || ua.indexOf('icab') != -1) {
      if (document.body && document.body.scrollTop != null) {
         return currentClientY - document.body.scrollTop;
      }
      return currentClientY;
   }
   
   // in IE and NS, a good clientY exists
   else if (currentClientY) {
      return currentClientY;
   }
   
   else {
      return null;
   }
};

// returns the distance from document left to event left
DOM2Event._getPageX = function(currentPageX, currentClientX) {
   var ua = navigator.userAgent.toLowerCase(); 

   // in cases where a pageX exists, it's good
	if (currentPageX) {
      return currentPageX;
   }
   
   // in IE, add scrollLeft to clientX
   else if (ua.indexOf("msie") != -1 && ua.indexOf("opera") == -1) {
      if (document.documentElement && document.documentElement.scrollLeft > 0) {
         return (currentClientX + document.documentElement.scrollLeft);
      }
      else if (document.body != null && document.body.scrollLeft > 0) {
         return (currentClientX + document.body.scrollLeft);
      }
		else {
			return currentClientX;
		}
   }
   
   // in Konqueror, Opera and iCab, clientX really contains the pageX value
   else if (currentClientX) {
      return currentClientX;
   }
   
   else {
      return null;
   }
};

// returns the distance from document top to event top
DOM2Event._getPageY = function(currentPageY, currentClientY) {
   var ua = navigator.userAgent.toLowerCase(); 

   // in cases where a pageY exists, it's good
	if (currentPageY) {
      return currentPageY;
   }
   
   // in IE, add scrollTop to clientY
   else if (ua.indexOf("msie") != -1 && ua.indexOf("opera") == -1) {
      if (document.documentElement && document.documentElement.scrollTop > 0) {
         return (currentClientY + document.documentElement.scrollTop);
      }
      else if (document.body != null && document.body.scrollTop > 0) {
         return (currentClientY + document.body.scrollTop);
      }
		else {
			return currentClientY;
		}
   }
   
   // in Konqueror, Opera and iCab, clientY really contains the pageY value
   else if (currentClientY) {
      return currentClientY;
   }
   
   else {
      return null;
   }
};