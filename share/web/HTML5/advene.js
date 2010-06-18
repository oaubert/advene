/*
 * ADAPTATION OF jQuery UI Dialog 1.7.2 TO CREATE THE WIDGET PLAYER
 *
 * Copyright (c) 2009 AUTHORS.txt (http://jqueryui.com/about)
 * Dual licensed under the MIT (MIT-LICENSE.txt)
 * and GPL (GPL-LICENSE.txt) licenses.
 *
 * http://docs.jquery.com/UI/Dialog
 *
 * Depends:
 *	ui.core.js
 *	ui.draggable.js
 *	ui.resizable.js
 */

(function($) {

var setDataSwitch = {
		dragStart: "start.draggable",
		drag: "drag.draggable",
		dragStop: "stop.draggable",
		maxHeight: "maxHeight.resizable",
		minHeight: "minHeight.resizable",
		maxWidth: "maxWidth.resizable",
		minWidth: "minWidth.resizable",
		resizeStart: "start.resizable",
		resize: "drag.resizable",
		resizeStop: "stop.resizable"
	},
	
	uiDialogClasses =
		'ui-dialog ' +
		'ui-widget ' +
		'ui-widget-content ' +
		'ui-corner-all ';

$.widget("ui.player", {

	_init: function() {
		this.originalTitle = this.element.attr('title');

		var self = this,
			options = this.options,

			title = options.title || this.originalTitle || '&nbsp;',
			titleId = $.ui.player.getTitleId(this.element),

			uiDialog = (this.uiDialog = $('<div/>'))
				.appendTo(document.body)
				.hide()
				.addClass(uiDialogClasses + options.dialogClass)
				.css({
					position: 'absolute',
					overflow: 'hidden',
					zIndex: options.zIndex
				})
				// setting tabIndex makes the div focusable
				// setting outline to 0 prevents a border on focus in Mozilla
				.attr('tabIndex', -1).css('outline', 0).keydown(function(event) {
					(options.closeOnEscape && event.keyCode
						&& event.keyCode == $.ui.keyCode.ESCAPE && self.close(event));
				})
				.attr({
					role: 'dialog',
					'aria-labelledby': titleId
				})
				.mousedown(function(event) {
					self.moveToTop(false, event);
				}),

			uiDialogContent = this.element
				.show()
				.removeAttr('title')
				.addClass(
					'ui-dialog-content ' +
					'ui-widget-content')
				.appendTo(uiDialog),

			uiDialogTitlebar = (this.uiDialogTitlebar = $('<div></div>'))
				.addClass(
					'ui-dialog-titlebar ' +
					'ui-widget-header ' +
					'ui-corner-all ' +
					'ui-helper-clearfix'
				)
				.prependTo(uiDialog),

			uiDialogTitlebarClose = $('<a href="#"/>')
				.addClass(
					'ui-dialog-titlebar-close ' +
					'ui-corner-all'
				)
				.attr('role', 'button')
				.hover(
					function() {
						uiDialogTitlebarClose.addClass('ui-state-hover');
					},
					function() {
						uiDialogTitlebarClose.removeClass('ui-state-hover');
					}
				)
				.focus(function() {
					uiDialogTitlebarClose.addClass('ui-state-focus');
				})
				.blur(function() {
					uiDialogTitlebarClose.removeClass('ui-state-focus');
				})
				.mousedown(function(ev) {
					ev.stopPropagation();
				})
				.click(function(event) {
					self.close(event);
					return false;
				})
				.appendTo(uiDialogTitlebar),

			uiDialogTitlebarCloseText = (this.uiDialogTitlebarCloseText = $('<span/>'))
				.addClass(
					'ui-icon ' +
					'ui-icon-closethick'
				)
				.text(options.closeText)
				.appendTo(uiDialogTitlebarClose),

			uiDialogTitle = $('<span/>')
				.addClass('ui-dialog-title')
				.attr('id', titleId)
				.html(title)
				.prependTo(uiDialogTitlebar);

		uiDialogTitlebar.find("*").add(uiDialogTitlebar).disableSelection();

		(options.draggable && $.fn.draggable && this._makeDraggable());
		(options.resizable && $.fn.resizable && this._makeResizable());

		this._createButtons(options.buttons);
		this._isOpen = false;

		(options.bgiframe && $.fn.bgiframe && uiDialog.bgiframe());
		(options.autoOpen && this.open());



 var self = this;
    
    this.uiDialog.bind('dragstop', function(event, ui) {
        if (self.options.sticky) {
            var left = Math.floor(ui.position.left) - $
(window).scrollLeft();
            var top = Math.floor(ui.position.top) - $(window).scrollTop
();
            self.options.position = [left, top];
        };
    });
    if (window.__dialogWindowScrollHandled === undefined) {
        window.__dialogWindowScrollHandled = true;
        $(window).scroll(function(e) {
            $('.ui-dialog-content').each(function() {
                var isSticky = $(this).player('option', 'sticky') && $(this).player('isOpen');
                if (isSticky) {
                    var position = $(this).player('option',
'position');
                    $(this).player('option', 'position', position);
                };
            });
        });
    };




		
	},

	destroy: function() {
		(this.overlay && this.overlay.destroy());
		this.uiDialog.hide();
		this.element
			.unbind('.dialog')
			.removeData('dialog')
			.removeClass('ui-dialog-content ui-widget-content')
			.hide().appendTo('body');
		this.uiDialog.remove();

		(this.originalTitle && this.element.attr('title', this.originalTitle));
	},

	close: function(event) {
		var self = this;
		
		if (false === self._trigger('beforeclose', event)) {
			return;
		}

		(self.overlay && self.overlay.destroy());
		self.uiDialog.unbind('keypress.ui-dialog');

		(self.options.hide
			? self.uiDialog.hide(self.options.hide, function() {
				self._trigger('close', event);
			})
			: self.uiDialog.hide() && self._trigger('close', event));

		$.ui.player.overlay.resize();

		self._isOpen = false;
		
		// adjust the maxZ to allow other modal dialogs to continue to work (see #4309)
		if (self.options.modal) {
			var maxZ = 0;
			$('.ui-dialog').each(function() {
				if (this != self.uiDialog[0]) {
					maxZ = Math.max(maxZ, $(this).css('z-index'));
				}
			});
			$.ui.player.maxZ = maxZ;
		}
	},

	isOpen: function() {
		return this._isOpen;
	},

	// the force parameter allows us to move modal dialogs to their correct
	// position on open
	moveToTop: function(force, event) {

		if ((this.options.modal && !force)
			|| (!this.options.stack && !this.options.modal)) {
			return this._trigger('focus', event);
		}
		
		if (this.options.zIndex > $.ui.player.maxZ) {
			$.ui.player.maxZ = this.options.zIndex;
		}
		(this.overlay && this.overlay.$el.css('z-index', $.ui.player.overlay.maxZ = ++$.ui.player.maxZ));

		//Save and then restore scroll since Opera 9.5+ resets when parent z-Index is changed.
		//  http://ui.jquery.com/bugs/ticket/3193
		var saveScroll = { scrollTop: this.element.attr('scrollTop'), scrollLeft: this.element.attr('scrollLeft') };
		this.uiDialog.css('z-index', ++$.ui.player.maxZ);
		this.element.attr(saveScroll);
		this._trigger('focus', event);
	},

	open: function() {
		if (this._isOpen) { return; }

		var options = this.options,
			uiDialog = this.uiDialog;

		this.overlay = options.modal ? new $.ui.player.overlay(this) : null;
		(uiDialog.next().length && uiDialog.appendTo('body'));
		this._size();
		this._position(options.position);
		uiDialog.show(options.show);
		this.moveToTop(true);

		// prevent tabbing out of modal dialogs
		(options.modal && uiDialog.bind('keypress.ui-dialog', function(event) {
			if (event.keyCode != $.ui.keyCode.TAB) {
				return;
			}

			var tabbables = $(':tabbable', this),
				first = tabbables.filter(':first')[0],
				last  = tabbables.filter(':last')[0];

			if (event.target == last && !event.shiftKey) {
				setTimeout(function() {
					first.focus();
				}, 1);
			} else if (event.target == first && event.shiftKey) {
				setTimeout(function() {
					last.focus();
				}, 1);
			}
		}));

		// set focus to the first tabbable element in the content area or the first button
		// if there are no tabbable elements, set focus on the dialog itself
		$([])
			.add(uiDialog.find('.ui-dialog-content :tabbable:first'))
			.add(uiDialog.find('.ui-dialog-buttonpane :tabbable:first'))
			.add(uiDialog)
			.filter(':first')
			.focus();

		this._trigger('open');
		this._isOpen = true;
	},

	_createButtons: function(buttons) {
		var self = this,
			hasButtons = false,
			uiDialogButtonPane = $('<div></div>')
				.addClass(
					'ui-dialog-buttonpane ' +
					'ui-widget-content ' +
					'ui-helper-clearfix'
				);

		// if we already have a button pane, remove it
		this.uiDialog.find('.ui-dialog-buttonpane').remove();

		(typeof buttons == 'object' && buttons !== null &&
			$.each(buttons, function() { return !(hasButtons = true); }));
		if (hasButtons) {
			$.each(buttons, function(name, fn) {
				$('<button type="button"></button>')
					.addClass(
						'ui-state-default ' +
						'ui-corner-all'
					)
					.text(name)
					.click(function() { fn.apply(self.element[0], arguments); })
					.hover(
						function() {
							$(this).addClass('ui-state-hover');
						},
						function() {
							$(this).removeClass('ui-state-hover');
						}
					)
					.focus(function() {
						$(this).addClass('ui-state-focus');
					})
					.blur(function() {
						$(this).removeClass('ui-state-focus');
					})
					.appendTo(uiDialogButtonPane);
			});
			uiDialogButtonPane.appendTo(this.uiDialog);
		}
	},

	_makeDraggable: function() {
		var self = this,
			options = this.options,
			heightBeforeDrag;

		this.uiDialog.draggable({
			cancel: '.ui-dialog-content',
			handle: '.ui-dialog-titlebar',
			containment: 'document',
			start: function() {
				heightBeforeDrag = options.height;
				$(this).height($(this).height()).addClass("ui-dialog-dragging");
				(options.dragStart && options.dragStart.apply(self.element[0], arguments));
			},
			drag: function() {
				(options.drag && options.drag.apply(self.element[0], arguments));
			},
			stop: function() {
				$(this).removeClass("ui-dialog-dragging").height(heightBeforeDrag);
				(options.dragStop && options.dragStop.apply(self.element[0], arguments));
				$.ui.player.overlay.resize();
			}
		});
	},

	_makeResizable: function(handles) {
		handles = (handles === undefined ? this.options.resizable : handles);
		var self = this,
			options = this.options,
			resizeHandles = typeof handles == 'string'
				? handles
				: 'se,sw';

		this.uiDialog.resizable({
			cancel: '.ui-dialog-content',
			alsoResize: this.element,
			maxWidth: options.maxWidth,
			maxHeight: options.maxHeight,
			minWidth: options.minWidth,
			minHeight: options.minHeight,
			ghost:true,
			start: function() {
				$(this).addClass("ui-dialog-resizing");
				(options.resizeStart && options.resizeStart.apply(self.element[0], arguments));
			},
			resize: function() {
				(options.resize && options.resize.apply(self.element[0], arguments));
			},
			handles: resizeHandles,
			stop: function() {
				$(this).removeClass("ui-dialog-resizing");
				options.height = $(this).height();
				options.width = $(this).width();
				(options.resizeStop && options.resizeStop.apply(self.element[0], arguments));
				$.ui.player.overlay.resize();
			}
		})
		.find('.ui-resizable-se').removeClass('ui-icon ui-icon-grip-diagonal-se');
	},

	_position: function(pos) {
		var wnd = $(window), doc = $(document),
			pTop = doc.scrollTop(), pLeft = doc.scrollLeft(),
			minTop = pTop;

		if ($.inArray(pos, ['center','top','right','bottom','left']) >= 0) {
			pos = [
				pos == 'right' || pos == 'left' ? pos : 'center',
				pos == 'top' || pos == 'bottom' ? pos : 'middle'
			];
		}
		if (pos.constructor != Array) {
			pos = ['center', 'middle'];
		}
		if (pos[0].constructor == Number) {
			pLeft += pos[0];
		} else {
			switch (pos[0]) {
				case 'left':
					pLeft += 0;
					break;
				case 'right':
					pLeft += wnd.width() - this.uiDialog.outerWidth();
					break;
				default:
				case 'center':
					pLeft += (wnd.width() - this.uiDialog.outerWidth()) / 2;
			}
		}
		if (pos[1].constructor == Number) {
			pTop += pos[1];
		} else {
			switch (pos[1]) {
				case 'top':
					pTop += 0;
					break;
				case 'bottom':
					pTop += wnd.height() - this.uiDialog.outerHeight();
					break;
				default:
				case 'middle':
					pTop += (wnd.height() - this.uiDialog.outerHeight()) / 2;
			}
		}

		// prevent the dialog from being too high (make sure the titlebar
		// is accessible)
		pTop = Math.max(pTop, minTop);
		this.uiDialog.css({top: pTop, left: pLeft});
	},

	_setData: function(key, value){
		(setDataSwitch[key] && this.uiDialog.data(setDataSwitch[key], value));
		switch (key) {
			case "buttons":
				this._createButtons(value);
				break;
			case "closeText":
				this.uiDialogTitlebarCloseText.text(value);
				break;
			case "dialogClass":
				this.uiDialog
					.removeClass(this.options.dialogClass)
					.addClass(uiDialogClasses + value);
				break;
			case "draggable":
				(value
					? this._makeDraggable()
					: this.uiDialog.draggable('destroy'));
				break;
			case "height":
				this.uiDialog.height(value);
				break;
			case "position":
				this._position(value);
				break;
			case "resizable":
				var uiDialog = this.uiDialog,
					isResizable = this.uiDialog.is(':data(resizable)');

				// currently resizable, becoming non-resizable
				(isResizable && !value && uiDialog.resizable('destroy'));

				// currently resizable, changing handles
				(isResizable && typeof value == 'string' &&
					uiDialog.resizable('option', 'handles', value));

				// currently non-resizable, becoming resizable
				(isResizable || this._makeResizable(value));
				break;
			case "title":
				$(".ui-dialog-title", this.uiDialogTitlebar).html(value || '&nbsp;');
				break;
			case "width":
				this.uiDialog.width(value);
				break;
		}

		$.widget.prototype._setData.apply(this, arguments);
	},

	_size: function() {
		/* If the user has resized the dialog, the .ui-dialog and .ui-dialog-content
		 * divs will both have width and height set, so we need to reset them
		 */
		var options = this.options;

		// reset content sizing
		this.element.css({
			height: 0,
			minHeight: 0,
			width: 'auto'
		});

		// reset wrapper sizing
		// determine the height of all the non-content elements
		var nonContentHeight = this.uiDialog.css({
				height: 'auto',
				width: options.width
			})
			.height();

		this.element
			.css({
				minHeight: Math.max(options.minHeight - nonContentHeight, 0),
				height: options.height == 'auto'
					? 'auto'
					: Math.max(options.height - nonContentHeight, 0)
			});
	}
});

$.extend($.ui.player, {
	version: "1.7.2",
	defaults: {
		autoOpen: true,
		bgiframe: false,
		buttons: {},
		closeOnEscape: true,
		closeText: 'close',
		dialogClass: '',
		draggable: true,
		sticky:false,
		hide: null,
		height: 'auto',
		maxHeight: false,
		maxWidth: false,
		minHeight: 150,
		minWidth: 150,
		modal: false,
		position: 'center',
		resizable: true,
		show: null,
		stack: true,
		title: '',
		width: 300,
		zIndex: 1000
	},

	getter: 'isOpen',

	uuid: 0,
	maxZ: 0,

	getTitleId: function($el) {
		return 'ui-dialog-title-' + ($el.attr('id') || ++this.uuid);
	},

	overlay: function(dialog) {
		this.$el = $.ui.player.overlay.create(dialog);
	}
});

$.extend($.ui.player.overlay, {
	instances: [],
	maxZ: 0,
	events: $.map('focus,mousedown,mouseup,keydown,keypress,click'.split(','),
		function(event) { return event + '.dialog-overlay'; }).join(' '),
	create: function(dialog) {
		if (this.instances.length === 0) {
			// prevent use of anchors and inputs
			// we use a setTimeout in case the overlay is created from an
			// event that we're going to be cancelling (see #2804)
			setTimeout(function() {
				// handle $(el).dialog().dialog('close') (see #4065)
				if ($.ui.player.overlay.instances.length) {
					$(document).bind($.ui.player.overlay.events, function(event) {
						var dialogZ = $(event.target).parents('.ui-dialog').css('zIndex') || 0;
						return (dialogZ > $.ui.player.overlay.maxZ);
					});
				}
			}, 1);

			// allow closing by pressing the escape key
			$(document).bind('keydown.dialog-overlay', function(event) {
				(dialog.options.closeOnEscape && event.keyCode
						&& event.keyCode == $.ui.keyCode.ESCAPE && dialog.close(event));
			});

			// handle window resize
			$(window).bind('resize.dialog-overlay', $.ui.player.overlay.resize);
		}

		var $el = $('<div></div>').appendTo(document.body)
			.addClass('ui-widget-overlay').css({
				width: this.width(),
				height: this.height()
			});

		(dialog.options.bgiframe && $.fn.bgiframe && $el.bgiframe());

		this.instances.push($el);
		return $el;
	},

	destroy: function($el) {
		this.instances.splice($.inArray(this.instances, $el), 1);

		if (this.instances.length === 0) {
			$([document, window]).unbind('.dialog-overlay');
		}

		$el.remove();
		
		// adjust the maxZ to allow other modal dialogs to continue to work (see #4309)
		var maxZ = 0;
		$.each(this.instances, function() {
			maxZ = Math.max(maxZ, this.css('z-index'));
		});
		this.maxZ = maxZ;
	},

	height: function() {
		// handle IE 6
		if ($.browser.msie && $.browser.version < 7) {
			var scrollHeight = Math.max(
				document.documentElement.scrollHeight,
				document.body.scrollHeight
			);
			var offsetHeight = Math.max(
				document.documentElement.offsetHeight,
				document.body.offsetHeight
			);

			if (scrollHeight < offsetHeight) {
				return $(window).height() + 'px';
			} else {
				return scrollHeight + 'px';
			}
		// handle "good" browsers
		} else {
			return $(document).height() + 'px';
		}
	},

	width: function() {
		// handle IE 6
		if ($.browser.msie && $.browser.version < 7) {
			var scrollWidth = Math.max(
				document.documentElement.scrollWidth,
				document.body.scrollWidth
			);
			var offsetWidth = Math.max(
				document.documentElement.offsetWidth,
				document.body.offsetWidth
			);

			if (scrollWidth < offsetWidth) {
				return $(window).width() + 'px';
			} else {
				return scrollWidth + 'px';
			}
		// handle "good" browsers
		} else {
			return $(document).width() + 'px';
		}
	},

	resize: function() {
		/* If the dialog is draggable and the user drags it past the
		 * right edge of the window, the document becomes wider so we
		 * need to stretch the overlay. If the user then drags the
		 * dialog back to the left, the document will become narrower,
		 * so we need to shrink the overlay to the appropriate size.
		 * This is handled by shrinking the overlay before setting it
		 * to the full document size.
		 */
		var $overlays = $([]);
		$.each($.ui.player.overlay.instances, function() {
			$overlays = $overlays.add(this);
		});

		$overlays.css({
			width: 0,
			height: 0
		}).css({
			width: $.ui.player.overlay.width(),
			height: $.ui.player.overlay.height()
		});
	}
});

$.extend($.ui.player.overlay.prototype, {
	destroy: function() {
		$.ui.player.overlay.destroy(this.$el);
	}
});


 




})(jQuery);

//////////////////  Variables de Contrôle
	
	var VideoURL="";
	var startMain=0;
	var videoMain;
	var isSliding=true;
	var bLoopInPlayer=false;

///////////////////////// Fonction Principale. Equivalente à Main()	

	$(function() {
/////////// REGLAGES POUR L'EXPORT
if (($("[target='video_player']").length == 0)) {return;}

$("[target='video_player']").each( function(){
val= $(this).attr('href');
$(this).attr('target','#');
diesePos=val.indexOf("#");
VideoURL=val.substring(0,diesePos);
$(this).click(function(){
val= $(this).attr('href');
diesePos=val.indexOf("#");
val=val.substring(diesePos+1);
 PlayFragment(val);return false;});
});
////////////////////////////////////////
$("body").append("<img class='player_minimized ui-corner-all' src='./resources/HTML5/maximized.png' ></img> <div id='player_container' class='player_container' style='position:relative;overflow:visible; '> <video id='mainV'   poster='adv.PNG' class='video' type='video/ogg;    codecs=theora, vorbis' oncanplay='canplayMain();' onloadstart='loadMain();' onwaiting='loadMain();' ondurationchange='changeMainDuration();' ontimeupdate='updateMain();' onpause='pauseMain();' onplaying='playMain();'style='overflow:visible; width:100%; border:thick #00FF00; '></video> <div id='fragment_info' style='position:absolute;top:10;left:20; color:#FFF ; width:auto;height:auto; overflow:visible '></div>  <div id='controles' class='controls ui-corner-all '>  <form id='controlesPlay' style='border:thick #00FF00'>      <object id='volumeUp'    class='ui-icon ui-icon-volume-on'   value='Volume Up'  onclick='' title='Volume Up'></object>      <object id='muted'    class='ui-icon ui-icon-volume-off'    value='Mute' onClick=''  title='Mute'></object>      <object id='play'    class='ui-icon ui-icon-play'  style='opacity:1;'  value='Play' onClick=''  title='Play' ></object>      <object id='pause'   class='ui-icon ui-icon-pause'    value='Pause' onClick=''  title='Pause' > </object>      <object id='stop'   class='ui-icon ui-icon-stop '    value='Stop' onClick=''  title='Stop' > </object>      <object id='playLoop'    class='ui-icon ui-icon-arrowrefresh-1-s'    value='LOOP' onClick=''  title='Start Loop Play'></object>      <object id='noplayLoop'    class='ui-icon ui-icon-arrowthickstop-1-e'    value='NO LOOP' onClick=''  title='Stop Loop Play'></object>      <object id='fragmentLoop' class='ui-icon ui-icon-refresh' style='opacity:0.5' value='Loop in Fragment' title='Loop in Fragment:off'></object>  </form>          <object id='timeLine'>          	<object id='slider-bubble' class='ui-corner-all'></object>          </object>                     <strong id='theTime' style=' right:8%;width:auto; position:absolute; font-size:10px'></strong>           <object id='close'   class='ui-icon ui-icon-closethick '  style=' right:1%; position:absolute; font-size:10px'  value='Close' onClick=''  title='Close the player' > </object>   <div id='volumeSliderContainer' style=' margin-top: 3px;	margin-bottom: 3px;clear: left; bottom:12; text-align:center; left:2;  overflow:visible;background-color:#999999; visibility:visible;height:50px; width:10; position:absolute; '> <object id='volumeSlider' style='height:90%; left:20%;width:40%; position:relative;'></object>    </div>  </div>    </div><div style='width:70%; padding:20;'> ");

videoMain=document.getElementById("mainV"); 
videoMain.src=VideoURL;
videoMain.load();
//////////////////////////////MAIN PLAYER CONTROL ////////////////////////////////////////////////////////////	
$("#muted").hide();
$("#pause").hide();
$("#controles").hide();
$("#playLoop").show();
$("#noplayLoop").hide();
$('#slider-bubble').hide();
$("#volumeSliderContainer").hide();
$('.player_container').player({
								title:'ADVENE MAIN PLAYER',
								position:['right',250],
							
								resizeStart: function(event, ui) {
								   $('.player_container').parents(".ui-dialog:first").find('.ui-dialog-content').show();
 								   $('#controles').css('visibility','hidden');
	   							},
								resizeStop: function(event, ui) {
									var hauteur=$("#mainV").position().top+$("#mainV").height();
									var largeur=$("#mainV").position().left+$("#mainV").width();
									$('.player_container').player('option', 'height', hauteur+30);
									$('.player_container').player('option', 'width', largeur+20);
									$('.player_container').parents(".ui-dialog:first").find('.ui-dialog-content').css('left',0);
									$("#mainV").css('left',10);
									$("#mainV").css('right',10);
									$('#controles').css('visibility','visible');
								}
});
$("div.player_container").mouseenter(function() { 
	var pos = $("#mainV").position();  
	var top = pos.top+$("#mainV").height()-15;
	var right = pos.left+$("#mainV").width();
	$("#controles").css('top',top);
	$("#controles").height(15);
	$("#controles").fadeIn("slow");
	return false;
});
		 
$("div.player_container").mouseleave(function() {
	$("#controles").fadeOut("slow");
	return false;
});


$("#play").click(
			   function(){
				  videoMain.play();
				  $("#play").hide();
				  $("#pause").show();
			   });

$("#pause").click(
			   function(){
				  videoMain.pause();
				  $("#play").show();
				  $("#pause").hide();
			   });

$("#stop").click(
			   function(){
				videoMain.pause();
				setMainTime(0);
				videoMain.removeEventListener("timeupdate",updatetime_main_listener, true);
				bLoopInPlayer=false;
				  LoopInPlayer();
			   });

$("#close").click(				  
			   function(){
				   if(bLoopInPlayer) {
					   $("#fragmentLoop").click();
					   $("#close").attr('title','Close the player');
					   }
					  else{
						  $("#stop").click(); 
						  $(this).parents().find('.player_container').player('close');
					  
					 }
				   });

$("#volumeUp")
	.click(
		function(){
		$(this).hide();$("#muted").show();
		videoMain.muted=true;
	})
.hover(
		function() {
		$("#volumeSliderContainer").show();
		},
		function() {
		$("#volumeSliderContainer").hide();
		}
	);

$("#volumeSliderContainer").hover(
		function() {
		$("#volumeSliderContainer").show();
		},
		function() {
		$("#volumeSliderContainer").hide();
		}
	);
$("#muted")
.click(
		function(){
		$(this).hide();$("#volumeUp").show();
		videoMain.muted=false;
		});
$("#volumeSlider").slider({
			orientation: "vertical",
			range: "min",
			min: 0,
			max: 100,
			value: 60,
			slide: function(event, ui) {
				var val = parseFloat($(this).slider("value"));
				val=val/100
				videoMain.volume=val;
			}
		});


$("#playLoop").click(
		function(){
		videoMain.loop=true;
		$("#playLoop").hide();
		$("#noplayLoop").show();
		});

$("#noplayLoop").click(
		function(){
		videoMain.loop=false;
		$("#noplayLoop").hide();
		$("#playLoop").show();
		});
		
$("#timeLine").slider({
			orientation: "horizontal",
			animate: true, 
			range: "min",
			min: 0,
			max: 100,
			value: 0,
			slide: function(event, ui) {
				videoMain.pause();
				updateValues(event, ui);				
			},
			start: function(event, ui) {
				isSliding=true;
				videoMain.pause();
				$('#slider-bubble').fadeIn();
				},
			stop: function(event, ui) {
				var duree=videoMain.duration;
				var val = parseFloat($(this).slider("value"));
				val=val*duree/100;
				setMainTime(val);
				setTimeout(function() {
					videoMain.play();
					 $('#slider-bubble').fadeOut("slow");
					}, 500);
			},
			change:function(event, ui) {
				isSliding=false;
				updateValues(event, ui);
			}
	});

$("#timeLine").removeClass('ui-corner-all');
var theTime=secondsToTime(videoMain.duration);
$("#theTime").text(' '+theTime.h+':'+theTime.m+':'+theTime.s);
////////////////// a supprimer ///////////////
$(".aMainPlay").click(
			   function(){
					
					$('.player_minimized:visible').click();
					setMainTime(toSeconds($(this).attr("value")));
					videoMain.play();

	   });
$(".fromToMainPlay").click(
			   function(){
					debut=toSeconds($(this).find('.instant_start:first').text());
					fin=toSeconds($(this).find('.instant_end:first').text());
					showInPlayerFromTo(debut,fin);

	   });
////////////////// FIN a supprimer ///////////////
$('#player_container').player('close');
$('.player_minimized')
	.hover(
						function() {
							$(this).css('background-color','#F00');
						},
						function() {
							$(this).css('background-color','#CCC');
						}
					)
	.focus(function() {
						$('.player_minimized').addClass('ui-state-focus');
				})
	.blur(function() {
						$('.player_minimized').removeClass('ui-state-focus');
				})
	.mousedown(function(ev) {
						ev.stopPropagation();
				})
	.click(function(event) {
		var options = { to: "#player_container", className: 'ui-effects-transfer' };
		$('.player_container').player('open');
		$('#player_container').css('top','0');
		$('.player_minimized').hide("transfer",options, 1000, function(){});
		$('.player_minimized').hide();
		return false;  
		});
	



/////////////////////////////MODIFICATION DE L'APPARENCE DE DIALOG: PLAYER PRINCIPAL //////////////////////////////

$('.ui-dialog-titlebar').each(function() {
					$(this).parents().find('.ui-dialog-titlebar-close').remove();

				uiDialogTitlebarToggle = $('<a href="#"/>')
				.addClass(
					'ui-dialog-titlebar-toggle ' +
					'ui-corner-all'
				)
				.attr('role', 'button')
				.hover(
					function() {
						uiDialogTitlebarToggle.addClass('ui-state-hover');
					},
					function() {
						uiDialogTitlebarToggle.removeClass('ui-state-hover');
					}
				)
				.focus(function() {
					uiDialogTitlebarToggle.addClass('ui-state-focus');
				})
				.blur(function() {
					uiDialogTitlebarToggle.removeClass('ui-state-focus');
				})
				.mousedown(function(ev) {
					ev.stopPropagation();
				})
				.click(function(event) {
					$(this).parents().find('.player_container').player('close');
					$(event.target).parents().find('.player_minimized').show();
					return false;
				})
				.appendTo($(this));

			uiDialogTitlebarToggleText = (this.uiDialogTitlebarToggleText = $('<span/>'))
				.addClass(
					'ui-icon ' +
					'ui-icon-minusthick'
				)
				.text('Toggle Player')
				.attr('title','Minimize Player')
				.appendTo(uiDialogTitlebarToggle);
///////////////////////////////////////////////////////////////////////////				
		uiDialogTitlebarFixonScreen = $('<a href="#"/>')
				.addClass(
					'ui-dialog-titlebar-fixonscreen ' +
					'ui-corner-all'
				)
				.attr('role', 'button')
				.hover(
					function() {
						uiDialogTitlebarFixonScreen.addClass('ui-state-hover');
					},
					function() {
						uiDialogTitlebarFixonScreen.removeClass('ui-state-hover');
					}
				)
				.focus(function() {
					uiDialogTitlebarFixonScreen.addClass('ui-state-focus');
				})
				.blur(function() {
					uiDialogTitlebarFixonScreen.removeClass('ui-state-focus');
				})
				.mousedown(function(ev) {
					ev.stopPropagation();
				})
				.click(function(event) {


					$(this).hide();
					$(this).parents().find('.ui-dialog').draggable('destroy');
				   	$(this).parents().find('.ui-dialog-titlebar-nofixonscreen').show();
					
					return false;
				})
				.appendTo($(this));

			uiDialogTitlebarFixonScreenText = (this.uiDialogTitlebarFixonScreenText = $('<span/>'))
				.addClass(
					'ui-icon ' +
					'ui-icon-pin-s'
				)
				.text("Fix On Screen")
				.attr('title','Fix Player position')
				.appendTo(uiDialogTitlebarFixonScreen);
	////////////////////////////////////////////////////////////////////////////////////


				uiDialogTitlebarNoFixonScreen = $('<a href="#"/>')
				.addClass(
					'ui-dialog-titlebar-nofixonscreen ' +
					'ui-corner-all'
				)
				.attr('role', 'button')
				.hover(
					function() {
						uiDialogTitlebarNoFixonScreen.addClass('ui-state-hover');
					},
					function() {
						uiDialogTitlebarNoFixonScreen.removeClass('ui-state-hover');
					}
				)
				.focus(function() {
					uiDialogTitlebarNoFixonScreen.addClass('ui-state-focus');
				})
				.blur(function() {
					uiDialogTitlebarNoFixonScreen.removeClass('ui-state-focus');
				})
				.mousedown(function(ev) {
					ev.stopPropagation();
				})
				.click(function(event) {
					$(this).hide();
					$(this).parents().find('.ui-dialog').draggable();
				   	$(this).parents().find('.ui-dialog-titlebar-fixonscreen').show();
										
					return false;
				})
				.appendTo($(this))
				.hide();

			uiDialogTitlebarNoFixonScreenText = (this.uiDialogTitlebarNoFixonScreenText = $('<span/>'))
				.addClass(				
						  'ui-icon ' +
					'ui-icon-pin-w'
				)
				.text('options')
				.attr('title','Stop Fixing Player position')
				.appendTo(uiDialogTitlebarNoFixonScreen);
	////////////////////////////////////////////////////////////////////////////////////

uiDialogTitlebarStickonWindow = $('<a href="#"/>')
				.addClass(
					'ui-dialog-titlebar-StickonWindow ' +
					'ui-corner-all'
				)
				.attr('role', 'button')
				.hover(
					function() {
						uiDialogTitlebarStickonWindow.addClass('ui-state-hover');
					},
					function() {
						uiDialogTitlebarStickonWindow.removeClass('ui-state-hover');
					}
				)
				.focus(function() {
					uiDialogTitlebarStickonWindow.addClass('ui-state-focus');
				})
				.blur(function() {
					uiDialogTitlebarStickonWindow.removeClass('ui-state-focus');
				})
				.mousedown(function(ev) {
					ev.stopPropagation();
				})
				.click(function(event) {
									
					$(this).hide();
					$.ui.player.sticky = true;
					$(this).parents().find('.player_container').player('option','sticky', true);
				   	$('.ui-dialog-titlebar-nostickonwindow').show();
				
					return false;
				})
				.appendTo($(this));

			uiDialogTitlebarStickonWindowText = (this.uiDialogTitlebarStickonWindowText = $('<span/>'))
				.addClass(				
						  'ui-icon ' +
					'ui-icon-locked'
				)
				.text('options')
				.attr('title','Lock Player on screen')
				.appendTo(uiDialogTitlebarStickonWindow);
	////////////////////////////////////////////////////////////////////////////////////


				uiDialogTitlebarNoStickonWindow = $('<a href="#"/>')
				.addClass(
					'ui-dialog-titlebar-noStickonWindow ' +
					'ui-corner-all'
				)
				.attr('role', 'button')
				.hover(
					function() {
						uiDialogTitlebarNoStickonWindow.addClass('ui-state-hover');
					},
					function() {
						uiDialogTitlebarNoStickonWindow.removeClass('ui-state-hover');
					}
				)
				.focus(function() {
					uiDialogTitlebarNoStickonWindow.addClass('ui-state-focus');
				})
				.blur(function() {
					uiDialogTitlebarNoStickonWindow.removeClass('ui-state-focus');
				})
				.mousedown(function(ev) {
					ev.stopPropagation();
				})
				.click(function(event) {
					$(this).hide();
					$(this).parents().find('.player_container').player('option','sticky', false);
				   	$('.ui-dialog-titlebar-stickonwindow').show();
					return false;
				})
				.appendTo($(this))
				.hide();
				

			uiDialogTitlebarNoStickonWindowText = (this.uiDialogTitlebarNoStickonWindowText = $('<span/>'))
				.addClass(				
						  'ui-icon ' +
					'ui-icon-unlocked'
				)
				.text('No Fix')
				.attr('title','Stop Locking Player on screen')
				.appendTo(uiDialogTitlebarNoStickonWindow);



	});

	// Extesnion de la classe Dialog pour pouvoir être Stickable
var _init = $.ui.player.prototype._init;
$.ui.player.prototype._init = function() {alert('ok');
    var self = this;
    _init.apply(this, arguments);
    this.uiDialog.bind('dragstop', function(event, ui) {
        if (self.options.sticky) {
            var left = Math.floor(ui.position.left) - $
(window).scrollLeft();
            var top = Math.floor(ui.position.top) - $(window).scrollTop
();
            self.options.position = [left, top];
        };
    });
    if (window.__dialogWindowScrollHandled === undefined) {
        window.__dialogWindowScrollHandled = true;
        $(window).scroll(function(e) {
            $('.ui-dialog-content').each(function() {
                var isSticky = $(this).player('option', 'sticky') && $(this).player('isOpen');
                if (isSticky) {
                    var position = $(this).player('option','position');
                    $(this).player('option', 'position', position);
                };
            });
        });
    };
};

$.ui.player.defaults.sticky = true;
// End of uiDialog widget extension... 
//////////////////////////////////////////////////////////////////////////////////////////////////////
	
});//////////// END MAIN
	
///////////////////////////////////////////////////////////	

/////////////////// DIFFERENTES FONCTIONS DE CONTROLE	
function LoopInPlayer(){
					
			if(bLoopInPlayer){
				setMainTime(startMain);
				$("#fragmentLoop").css('opacity',1.0);
				$("#fragmentLoop").attr('title','Loop in Fragment: ON');
				$('.player_container').player('option', 'title', 'FRAGMENT PLAY');
			
			}
			else{
				$("#fragmentLoop").css('opacity',0.5);
				$("#fragmentLoop").attr('title','Loop in Fragment: OFF');
				$('.player_container').player('option', 'title', 'ADVENE MAIN PLAYER');
				$("#fragment_info").fadeOut("slow");
			}
}
function showInPlayerFromTo(debut,fin){
		videoMain.pause();
		videoMain.removeEventListener("timeupdate",updatetime_main_listener, true);
		imgToggled= 0;
		endMain=fin;
		startMain=debut;
		setMainTime(debut);

		videoMain.addEventListener("timeupdate",updatetime_main_listener, true);
		$('.player_minimized:visible').click();
		bLoopInPlayer=true;
		LoopInPlayer();
		//////// afficher legende
		$("#fragment_info").text("");
		$("#fragment_info").fadeIn("slow");
		//////////////////////////
		$("#close").attr('title','Close the Fragment');
		//videoMain.play();
}	
function showInPlayer(sb){
		videoMain.pause();
		videoMain.removeEventListener("timeupdate",updatetime_main_listener, true);
		var s=$(sb).parent();
		var options = { to: "#mainV", className: 'ui-effects-transfer' };
		$(s).effect("transfer",options, 2000, function(){
		
		if(imgToggled!= 0) {$(imgToggled).fadeIn('slow');}
		imgToggled= 0;
		
		var debut=toSeconds($(sb).parents('div:first').children().find('.instant_start').text());
		var fin=toSeconds($(sb).parents('div:first').children().find('.instant_end').text());

		endMain=fin;
		startMain=debut;
		setMainTime(debut);
		
		videoMain.addEventListener("timeupdate",updatetime_main_listener, true);
		bLoopInPlayer=true;

		LoopInPlayer();

		//////// afficher légende
		$("#fragment_info").text($(sb).parents('div:first').children('div:first').find('strong').text()		);
		$("#fragment_info").fadeIn("slow");
		//////////////////////////
		$("#close").attr('title','Close the Fragment');
		videoMain.play();
	
		});
		
}
	
function updatetime_main_listener(){
		
			if(bLoopInPlayer){			
			if(endMain<=getMainTime()) {
			setMainTime(startMain);
				}
			}
}
	


function loadMain(){
	
			var load= $('<strong/>')
					.attr('class', 'heading ui-corner-all')
					.text('LOADING')
					.prependTo("#player_container").fadeIn(300);
}

function canplayMain(){
			
			$("#player_container .heading").fadeOut("slow",function(){
  			 $("#player_container .heading").remove(); });			
}



function playMain(){
			$("#pause").show();
			$("#play").hide();
			
			var duree=100;//videoMain.duration;
			var time=getMainTime();
			var val=parseFloat((time*100)/duree);
			$("#timeLine").slider('option','value', val );
}

function updateMain(){
		if(isSliding) return;
		var time=getMainTime();
		var duree=100;//videoMain.duration;
		var val=parseFloat((time*100)/duree);
		$("#timeLine").slider('option','value', val );		
}

function pauseMain(){
			$("#pause").hide();
			$("#play").show();
}


		
function changeMainDuration(){
	theTime=secondsToTime(videoMain.duration);
	$("#theTime").text(' '+theTime.h+':'+theTime.m+':'+theTime.s);
}
 
function updateValues(event, ui){
		var valeur=$("#timeLine").slider('value');
		var duree=100;//videoMain.duration;
		var theTime=secondsToTime(parseFloat((valeur*duree)/100));
		var t=theTime.h+':'+theTime.m+':'+theTime.s;
		var offset1 = $('#timeline .ui-slider-handle').position();
        $('#slider-bubble').text(t).css({'left':offset1.left - 20	});
}
function getMainTime(){
var t;
try
  {
  t=videoMain.currentTime;
  }
catch(err)
  {
  txt="There was an error on this page.\n\n";
  txt+="Error description: " + err.description + "\n\n";
  txt+="Click OK to continue.\n\n";
  alert(txt);return 0;
  }
return t;
}
function setMainTime(t){
	try{
	videoMain.currentTime=t; 
	}
	catch(e){}
}
function toSeconds(str) {

        var s = str.split(':');
        s[3] = s[2].split('.')[1];
        s[2] = s[2].split('.')[0];
		return (parseInt(s[2], 10) + s[0] * 3600 + s[1] * 60 + s[3] / 1000); 
      }

function secondsToTime(secs){
	if(isNaN(secs)) {
		 var obj = {
        "h": 0,
        "m": 0,
        "s": 0
		};
	return obj;
	}
    var hours = Math.floor(secs / (60 * 60));
    var divisor_for_minutes = secs % (60 * 60);
    var minutes = Math.floor(divisor_for_minutes / 60);
    var divisor_for_seconds = divisor_for_minutes % 60;
    var seconds = Math.ceil(divisor_for_seconds);

    var obj = {
        "h": hours,
        "m": minutes,
        "s": seconds
    };
    return obj;
}
function PlayFragment(t) {
					$('.player_minimized:visible').click();
					setMainTime(t);
					videoMain.play();
      }

