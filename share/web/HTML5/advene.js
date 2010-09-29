/*
L'API consiste en quatre widgets principales permettant de définir des vignettes, players vignettes et players autonomes faisant appel aux services de html5 video
*/

/**
 * @private
 */
_formatTime = function( seconds ) {
	var h = parseInt(seconds / 3660);
	var m = parseInt((seconds / 60)-(h*60));
	var s = Number(seconds % 60).toPrecision(3);
    // 0-padding
	var hp = h >= 10 ? '' : '0';
	var mp = m >= 10 ? '' : '0';
	var sp = s >= 10 ? '' : '0';
	return hp + h + ':' + mp + m + ":" + sp + s
};
    

// L'outil video prend en charge les spécifications html5 video pour les besoins de l'API. Lors d'une instanciation d'une balise video en une instance video(), les options suivantes peuvent être incluses:
// ** Options standard
//	- VideoURL
//	- autoplay: lecture automatique
// 	- loop
// 	- autoBuffer
// 	-volume
// ** Options propres à l'API
// 	-vignet: indique si le lecteur est un lecteur vignette (true) ou bien si c'est un lecteur autonome (classe player)
//	-fragmentPlay: cette option indique si la lecture est sur un fragment délimité ou non. On a vignet=true ---> fragmentPlay=true
//	-startPoint et endpoint: début et fin du fragment ou de la vidéo
//	-endFragmentBehaviour: loop, pause, continue
$.widget("ui.video", {
	// default options
	options: {
		VideoURL: "",
		autoPlay: false,
		loop: false,
		autoBuffer: true,
		volume: .5,
		vignet: false,
		fragmentPlay: false,
		startPoint: 0,
		endPoint: 0,
		endFragmentBehaviour: "continue",
        transcriptHighlight: true,
        location: { 'left': 0, 'top': 0 }
	},
    
	_create: function() {
	    //  	Paramètrage avec les options nécessaires et celles spécifiées lors de l'instanciation
		var videoOptions = {
			autoplay: this.options.autoPlay,
			controls: false,
			loop: this.options.loop,
			autobuffer: this.options.autoBuffer
		};
        
		/**
		 * @type {!Object}
		 * @private
		 */
		this._container = this.element.parent();
		if (this.options.vignet)
            this.options.fragmentPlay=true;
        
		/**
		 * @type {!Object}
		 * @private
		 */
		this._oldVideooptions = {};
        
		$.each( videoOptions , function( key, value) {
			if( value !== null ) {
				// webkit bug
				if( key == 'autoplay' && $.browser.webkit ) {
					value = false;
				}
				this._oldVideooptions[key] = this.element.attr( key );
				this.element.attr( key, value );
			}
		}
			  );
        
	    //  	Gestion des événements du playback vidéo
		var videoEvents = [
			"abort",
			"canplay",
			"canplaythrough",
			"canshowcurrentframe",
			"dataunavailable",
			"durationchange",
			"emptied",
			"empty",
			"ended",
			"error",
			"loadedfirstframe",
			"loadedmetadata",
			"loadstart",
			"pause",
			"play",
			"progress",
			"ratechange",
			"seeked",
			"seeking",
			"suspend",
			"timeupdate",
			"volumechange",
			"waiting",
            
		];
        
		$.each( videoEvents, function(){
			if( this["_event_" + this] ) {
				this.element.bind(
					this + ".video",
					$.proxy(this["_event_" + this],this)
				);
			} else {
				this.element.bind(
					this + ".video",
					$.proxy(function(){
						//alert("event "+ this+"  not implemented");
					},
							this
						   )
				);
			}
		}
			  );
        
	    //  	Instanciation de la barre de contrôle et définition de son comportement (apparition lors du survol de la vidéo)
		this._createControls();
		this._container.hover(
			$.proxy(this._showControls,this),
			$.proxy(this._hideControls,this)
		);
        
	    //  	Indicatif d'attente
		/**
		 * @type {!Object}
		 * @private
		 */
		this._waitingContainer = $('<div/>', {'class': 'ui-video-waiting-container'});

		/**
		 * @type {!Object}
		 * @private
		 */
		this._waiting = $('<div/>', {'class': 'ui-video-waiting'}).appendTo(this._waitingContainer);
        
		this._controls
			.fadeIn(500)
			.delay(100)
			.fadeOut(500);
        
		this._volumeSlider.slider('value', this.options.volume * 100);
        
		// webkit bug
		if( this.options.autoPlay && $.browser.webkit ) {
			this.play();
		}
	},
	// 	Fonction privée de création de contrôles
	_createControls: function() {
		vigneText = '';
		if (this.options.vignet) {
            vigneText='-vign';
        }
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._controls = $('<div/>',
				           {
					           'class': ' ui-corner-all ui-video-control'+vigneText
				           }
			              )
			.prependTo(this._container);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._progressDiv = $('<div/>',
				              {
					              'class': 'ui-video-progress'
				              }
			                 )
			.appendTo(this._controls);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._currentProgressSpan = $('<span/>',
				                      {
					                      'class': 'ui-video-current-progress', 'text': '00:00'
				                      }
			                         )
			.appendTo(this._progressDiv);
        
		$('<span/>',
		  {
			  'html': '/',
			  'class': 'ui-video-progress-divider'
		  }
		 )
			.appendTo(this._progressDiv);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._durationSpan = $('<span/>',
				               {
					               'class': 'ui-video-length', 'text': '00:00'
				               }
			                  )
			.appendTo(this._progressDiv);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
        
		this._muteButton = $('<div/>',
				             {
					             'class': 'ui-icon ui-icon-volume-on ui-video-mute'+vigneText
				             }
			                )
			.appendTo(this._controls)
			.bind('click.video', $.proxy(this._mute,this));
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._playButton = $('<div/>',
				             {
					             'class': 'ui-icon ui-icon-play ui-video-play'+vigneText
				             }
			                )
			.appendTo(this._controls)
			.bind('click.video', $.proxy(this._togglePlayPause,this));
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._stopButton = $('<div/>',
				             {
					             'class': 'ui-icon ui-icon-stop ui-video-stop'+vigneText
				             }
			                )
			.appendTo(this._controls)
			.bind('click.video', $.proxy(this._stopfragmentplay,this))
			.bind('click.video', $.proxy(this._stop,this));
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._playLoopButton = $('<div/>',
				                 {
					                 'class': 'ui-icon ui-icon-arrowrefresh-1-s ui-video-playLoop'+vigneText
				                 }
			                    )
			.appendTo(this._controls)
			.bind('click.video', $.proxy(this._tooglePlayLoop,this));
        

		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._stopFragmentLoop = $('<div/>',
				                   {
					                   'class': 'ui-icon ui-icon-closethick ui-video-fragmentLoop'+vigneText
				                   }
			                      )
			.appendTo(this._controls)
			.hide()
			.bind('click.video', $.proxy(this._stopfragmentplay,this));
        
        
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._volumeSlider = $('<div/>',
				               {
					               'class': 'ui-video-volume-slider'+vigneText
				               }
			                  )
			.appendTo(this._controls)
			.slider({
				range: 'min',
				animate: true,
				stop: function( e, ui ) {
					ui.handle.blur();
				},
				slide: function( e, ui ) {
					this.volume.apply(this,[ui.value]);
					return true;
				}
			}
			       );
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._timeLinerSliderHover =  $('<div/>',
				                        {
					                        'class': 'ui-widget-content ui-corner-all ui-video-timeLiner-slider-hover'
				}
			                           )
			.hide();
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._timeLinerSlider = $('<div/>',
				                  {
					                  'class': 'ui-video-timeLiner-slider'+vigneText
				                  }
			                     )
			.appendTo(this._controls)
			.slider({
				range: 'min',
				animate: true,
				start: function( e, ui ) {
					if( this.element[0].readyState === HTMLMediaElement.HAVE_NOTHING ) {
						return false;
					} else {
						this._timeLinerSliderHover.fadeIn('fast');
						this._timeLinerHoverUpdate.apply(this,[ui.handle, ui.value]);
						return true;
					}
				},
				stop: function( e, ui ) {
                    
					ui.handle.blur();
					if( this._timeLinerSliderHover.is(':visible') ) {
						this._timeLinerSliderHover.fadeOut('fast');
					}
                    
					if( this.element[0].readyState === HTMLMediaElement.HAVE_NOTHING ) {
						return false;
					} else {
						this._currentProgressSpan.text(_formatTime(this.element[0].duration * (ui.value/100)));
						return true;
					}
				},
				slide: function( e, ui ) {
					if( this.element[0].readyState === HTMLMediaElement.HAVE_NOTHING ) {
						return false;
					} else {
						this._timeLinerHoverUpdate.apply(this,[ui.handle, ui.value]);
						this.timeline.apply(this,[ui.value]);
						return true;
					}
				}
			}
			       );
        
		this._timeLinerSliderHover.appendTo(this._timeLinerSlider);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._timeLinerSliderAbsoluteWidth = this._timeLinerSlider.width();
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._bufferStatus = $('<div/>',
				               {
					               'class': 'ui-video-buffer-status ui-corner-all'
				               }
			                  ).appendTo( this._timeLinerSlider );
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		this._stopFragmentButton = $('<div/>',
				                     {
					                     'class': 'ui-icon ui-icon-closethick ui-video-fragment-close'+vigneText
				                     }
			                        )
			.appendTo(this._controls)
			.bind('click.video', $.proxy(this._closeFragment,this));
	},
	/**
	 * @private
	 */
	_timeLinerHoverUpdate: function( elem, value ) {
		var duration = this.element[0].duration;
        
		this._timeLinerSliderHover
			.text(_formatTime(duration * (value/100)))
			.position({
				'my': 'bottom',
				'at': 'top',
				'of': elem,
				'offset': '0 -10',
				'collision': 'none'
			}
			         );
        
        
	},
	/**
	 * @private
	 */
	_togglePlayPause: function() {
		if( this.element[0].paused ) {
			this.play();
		} else {
			this.pause();
		}
	},
	/**
	 * @private
	 */
	_stop: function() {
		this.stop();
	},
	_tooglePlayLoop: function() {
		if (this.element[0].loop) { 
            this.element[0].loop=false;
		    this._playLoopButton.removeClass('ui-icon-arrowthickstop-1-e').addClass('ui-icon-arrowrefresh-1-s');
        } else {
            this.element[0].loop=true;
			this._playLoopButton.addClass('ui-icon-arrowthickstop-1-e').removeClass('ui-icon-arrowrefresh-1-s');
        }
	},
	/**
	 * @private
	 */
	_stopfragmentplay: function() {
		this.options.fragmentPlay=false;
		this._stopFragmentLoop.hide();
		this._container.parent().find(".ui-dialog-fragment-title").hide();
		this._container.parent().find(".ui-dialog-fragment-title").text("Fragment PLAY");
	},
	/**
	 * @private
	 */
	_mute: function() {
		var muted = this.element[0].muted = !this.element[0].muted;
		this._muteButton.toggleClass('ui-icon-volume-on', !muted).toggleClass('ui-icon-volume-off', muted);
	},
	/**
	 * @private
	 */
	_hideControls: function() {
		this._controls
			.stop(true,true)
			.delay(100)
			.fadeOut(500);
	},
	/**
	 * @private
	 */
	_showControls: function(){
		this._controls
			.stop(true,true)
        
			.fadeIn(500);
	},
	/**
	 * @private
	 */
	_hideWaiting: function(){
		if( this._waitingId ) {
			clearInterval( this._waitingId );
			this._waitingId = null;
			this._waitingContainer.fadeOut('fast').remove();
		}
	},
	/**
	 * @private
	 */
	_showWaiting: function(){
		if( ! this._waitingId ) {
			this._waiting.css('left', 0);
			this._waitingContainer
				.appendTo(this._container)
				.position({
					'my': 'center',
					'at': 'center',
					'of': this.element,
					'collision': 'none'
				}
				         ).fadeIn('fast');
			var waitingWidth = this._waiting.width();
			var _waitingContainerWidth = this._waitingContainer.width();
			this._waitingId = setInterval(function() {
				var cur_left = Math.abs(this._waiting.position().left);
                
				this._waiting.css({'left': -((cur_left + _waitingContainerWidth) % waitingWidth) });
                
			}, 50);
		}
	},

	/**
	 * @private
	 */
	_closeFragment: function() {
		this._container.parent().find('.video-container:first').trigger("destroySamplePlayer");
        
	},

	// Events
	/**
	 * @private
	 */
	_event_progress: function(e) {
		var lengthComputable = e.originalEvent.lengthComputable,
		loaded = e.originalEvent.loaded,
		total = e.originalEvent.total;
        
		if( lengthComputable ) {
			var fraction = Math.max(Math.min(loaded / total,1),0);
            
			this._bufferStatus.width(Math.max(fraction * this._timeLinerSliderAbsoluteWidth));
		}
        
	},
	/**
	 * @private
	 */
	_event_seeked: function() {
		this._hideWaiting();
	},
	/**
	 * @private
	 */
	_event_canplay: function() {
		this._hideWaiting();
	},
	/**
	 * @private
	 */
	_event_loadstart: function() {
		this._showWaiting();
	},
	/**
	 * @private
	 */
	_event_durationchange: function() {
		this._showWaiting();
	},
	/**
	 * @private
	 */
	_event_seeking: function() {
		this._showWaiting();
	},
	/**
	 * @private
	 */
	_event_waiting: function() {
		this._showWaiting();
	},
	/**
	 * @private
	 */
	_event_loadedmetadata: function() {
		this._durationSpan.text(_formatTime(this.element[0].duration));
	},
	/**
	 * @private
	 */
	_event_play: function() {
		this._playButton.addClass('ui-icon-pause').removeClass('ui-icon-play');
	},
	/**
	 * @private
	 */
	_event_pause: function() {
		this._playButton.removeClass('ui-icon-pause').addClass('ui-icon-play');
	},

	/**
	 * @private
	 */
	/**
	 * @private
	 */
	_event_timeupdate: function() {
		if( ! this.element[0].seeking ) {
			var duration = this.element[0].duration;
			var currentTime = this.element[0].currentTime;
            
			if (((currentTime > this.options.endPoint) || (currentTime<this.options.startPoint)) && (this.options.fragmentPlay))
			{
				switch(this.options.endFragmentBehaviour)
				{
				case "continue":
					this._stopfragmentplay();
					break;
				case "pause":
					this._stopfragmentplay();
					this.pause();
					break;
				case "stop":
					this._stopfragmentplay();
					this.stop();
					break;
				default: // LOOP
					this.element[0].currentTime = this.options.startPoint;
				}
				return;
			}
            
            // Highlight/unhighlight elements by using the .activeTranscript class
            if (this.options.transcriptHighlight)
                $(".transcript[data-begin]", $(document)).each( function() {
                    if ($(this).hasClass('activeTranscript'))
                    {
                        if (currentTime < $(this).attr('data-begin') || currentTime > $(this).attr('data-end'))
                            $(this).removeClass('activeTranscript')
                    } else {
                        if ($(this).attr('data-begin') <= currentTime && currentTime <= $(this).attr('data-end'))
                            $(this).addClass('activeTranscript')                    
                    }
                });
                   
			this._timeLinerSlider.slider(
				'value',
				[(currentTime / (this.element[0].duration)) * 100]
			);
            
			this._durationSpan.text(_formatTime(this.element[0].duration));
			this._currentProgressSpan.text(_formatTime(currentTime));
            
		}
	},
	_wait: function(t) {
		var date = new Date();
		var curDate = null;
		do {
            curDate = new Date();
        } while (curDate - date < t);
	},
    
	/**
	 * @private
	 */
	_event_resize: function() {
        alert('_event_resize');
		this._controls.position({
			'my': 'bottom',
			'at': 'bottom',
			'of': this.element,
			'offset': '0 -10',
			'collision': 'none'
		}
			                   );
		this._container.width( this.element.outerWidth(true) );
		this._container.height( this.element.outerHeight(true) );
	},
    
	// User functions
	getIntrinsicWidth: function() {
        this._wait(500);
		return (this.element[0].videoWidth);
        
	},
	getIntrinsicHeight: function() {
		return (this.element[0].videoHeight);
	},
	play: function() {
		this.element[0].play();
	},
	pause: function() {
		this.element[0].pause();
	},
	stop: function() {
		this.fragmentLoop = false;
		this.element[0].currentTime = 0;
		this.element[0].pause();
		this._timeLinerSlider.slider('value', 0);
		this._currentProgressSpan.text(_formatTime(0));


	},
	mute: function() {
		this.element[0].muted = true;
	},
	unmute: function() {
		var this = this;
		this.element[0].muted = false;
	},
	rewind: function() {
		var this = this;
		this.element[0].playbackRate -= 2;
	},
	forward: function() {
		var this = this;
		this.element[0].playbackRate += 2;
	},
	volume: function(vol) {
		var this = this;
		this.element[0].volume = Math.max(Math.min(parseInt(vol) / 100, 1), 0);
	},
	timeline: function(pos){
		var this = this;
		var duration= this.element[0].duration;
		var pos = Math.max(Math.min(parseInt(pos) / 100, 1), 0);
		this.element[0].currentTime = duration * pos;
	},
	setPlayingTime: function(pos){
		var this = this;
		try{
			this.element[0].currentTime = pos;
			this.play();
		}
		catch(e){}
        
	},
	fragmentPlay: function(debut, fin, endFragBehav) {
		var this = this;
        this.element[0].load();
		setTimeout(function() {            
			this.options.endPoint = fin > 0 ? fin:this.element[0].duration;
			this.options.startPoint = debut;
			this.options.fragmentPlay = true;
			this.options.endFragmentBehaviour = endFragBehav;
			this._stopFragmentLoop.show();
			this.setPlayingTime(debut);
		}, 500);

	},

	// The destroyer
	destroy: function() {
		var this = this;
		$.each( this._oldVideooptions , function( key, value) {
			this.element.attr( key, value );
		}
			  );
        
		this._controls.remove();
		this.element.unwrap();
		this.element.unbind( ".video" );
		$.Widget.prototype.destroy.apply(this, arguments); // default destroy
	}
});

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////// MAIN PLAYER WIDGET ////////////////////////////////////////////////////////////
// L'outil player définit un lecteur html5 video. Il instancie un objet video() en lui définissant un conteneur indépendant. Le conteneur lui-même est dérivé de ui.dialog de jquery auquel un certain nombre de fonctions ont été greffées
// pour le compte de l'application
(function($) {
    player=$.extend({}, $.ui.dialog.prototype);
    $.widget("ui.player", $.ui.dialog, player);
    var _init = $.ui.player.prototype._init;

    $.ui.player.prototype._init = function() {
        var options = this.options;
        var videoObject;

        options.closeOnEscape = false;
        _init.apply(this, arguments);
        uiPlayer=this.uiDialog;

        ////////////// CREATE MINIMIZED ICON FOR PLAYER
        this.minplayer=$('<img/>',
				         {
					         'class': ' ui-corner-all player_minimized',
					         'src': './resources/HTML5/maximized.png',
					         'title': this.options.title+' Click to restore'
				         }
			            )
			.appendTo(uiPlayer.parent())
			.hide()
			.draggable()
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
				var options = { 
                    to: ".player_container", 
                    className: 'ui-effects-transfer' 
                };
				this.uiDialog.show();
				//('.player_container').player('open');
				//this.minplayer.css('top','0');
				this.minplayer.hide("transfer", options, 1000, function(){} );
				this.minplayer.hide();
				return false;
			})
        
        ///////////////////////////////////////////////////////
      


        uiPlayer
	        .bind('dragstop', function(event, ui) {
	           
	        })
	        .bind('resizestart', function(event, ui) {
	            
	        })
	        .bind('resizestop', function(event, ui) {
	            vid = uiPlayer.find('video', this);
		        content=uiPlayer.find('.ui-dialog-content ', this);
		        control=uiPlayer.find('.ui-video-control ', this);
		        $(vid).position({
		            my: "top",
		            at:"top",
		            of: content,
		            offset: "2",
		            collision: "none"
		        });

		        var hauteur= $(vid).position().top + $(vid).height();
		        var largeur= $(vid).position().left + $(vid).width();
		        uiPlayer.css({
                    'width': largeur + 2,
                    'height': hauteur + 20
                });
		        $(content).css({
                    'height': hauteur
                });
	            $(control).position({
		            my: "top",
		            at: "top",
		            of: uiPlayer,
		            offset: hauteur - 30,
		            collision: "none"
		        });
	        });

       
        
        uiPlayer = this.uiDialog;

        videoObject = uiPlayer.find('video', this);
        videoObject.video();
        videoObject.video('option', 'endFragmentBehaviour', 'continue');
        
        uiPlayer.find('.ui-dialog-titlebar-close ', this).remove();
        
        uiPlayerTitlebar=uiPlayer.find('.ui-dialog-titlebar ', this);
        
        ///////////// TITRE DU FRAGMENT
        uiPlayerFragmentTitle = $('<strong/>')
		    .text("Fragment PLAY")
		    .addClass("ui-dialog-fragment-title")
		    .hide()
		    .appendTo(uiPlayer);
        
        /////////////////////////////// AJOUT DE FONCTIONS A L'INTERFACE
	    // 	Fonction de minimisation en icone
	    uiPlayerTitlebarToggle = $('<a href="#"/>')
		    .addClass('ui-dialog-titlebar-toggle ' + 'ui-corner-all')
		    .attr('role', 'button')
		    .hover(
			    function() { $(this).addClass('ui-state-hover'); },
			    function() { $(this).removeClass('ui-state-hover'); }
		    )
		    .focus(function() { $(this).addClass('ui-state-focus'); })
		    .blur(function() { $(this).removeClass('ui-state-focus'); })
		    .mousedown(function(ev) { ev.stopPropagation();	})
		    .click(function(event) { 
                this.uiDialog.hide();
                this.minplayer.show();
				return false;
			})
		    .appendTo(uiPlayerTitlebar);
        
	    uiPlayerTitlebarToggleText = (this.uiPlayerTitlebarToggleText = $('<span/>'))
		    .addClass('ui-icon ' +'ui-icon-minusthick')
		    .text('Toggle Player')
		    .attr('title','Minimize Player')
		    .appendTo(uiPlayerTitlebarToggle);
        
	    // 	Fonction de fixation sur la page --> le player ne peut être déplacé à la souris
	    uiPlayerTitlebarFixonScreen = $('<a href="#"/>')
		    .addClass('ui-dialog-titlebar-fixonscreen ' +'ui-corner-all')
		    .attr('role', 'button')
		    .hover(function() {$(this).addClass('ui-state-hover');},
			       function() {$(this).removeClass('ui-state-hover');}
			      )
		    .focus(function() {$(this).addClass('ui-state-focus');})
		    .blur(function() {$(this).removeClass('ui-state-focus');	})
		    .mousedown(function(ev) {
			    ev.stopPropagation();
		    })
		    .click(function(event) {
			    $(this).hide();
			    uiPlayer.css('position','fixed');
			    this.uiDialog.find('.ui-dialog-titlebar-nofixonscreen ',this).show();
			    return false;
		    })
		    .appendTo(uiPlayerTitlebar);
        
	    uiPlayerTitlebarFixonScreenText = (this.uiPlayerTitlebarFixonScreenText = $('<span/>'))
		    .addClass('ui-icon ' +'ui-icon-pin-s')
		    .text("Fix On Screen")
		    .attr('title','Fix Player On Screen (fixed)')
		    .appendTo(uiPlayerTitlebarFixonScreen);
        
	    // 	Fonction de non fixation sur la page --> le player peut être désormais déplacé à la souris
	    uiPlayerTitlebarNoFixonScreen = $('<a href="#"/>')
		    .addClass('ui-dialog-titlebar-nofixonscreen ' +'ui-corner-all')
		    .attr('role', 'button')
		    .hover(
                function() { $(this).addClass('ui-state-hover'); },
			    function() { $(this).removeClass('ui-state-hover'); }
			)
		    .focus(function() { $(this).addClass('ui-state-focus');} )
		    .blur(function() { $(this).removeClass('ui-state-focus'); } )
		    .mousedown(function(ev) { ev.stopPropagation(); } )
		.click(function(event) {
			$(this).hide();
			uiPlayer.css('position','absolute');
			this.uiDialog.find('.ui-dialog-titlebar-fixonscreen ').show();
			return false;
		})
		    .appendTo(uiPlayerTitlebar)
		    .hide();
        
	    uiPlayerTitlebarNoFixonScreenText = (this.uiPlayerTitlebarNoFixonScreenText = $('<span/>'))
		    .addClass('ui-icon ' +'ui-icon-pin-w')
		    .text('options')
		    .attr('title','Fix Player on its Page (absolute)')
		    .appendTo(uiPlayerTitlebarNoFixonScreen);
        
      
        
        //////////////////////////////////////////////
        this.fragmentPlay = function(debut, fin, title, endFragBehav) {
            videoObject.video('fragmentPlay', debut, fin, this.options.endFragmentBehaviour);
            uiPlayer.find(".ui-dialog-fragment-title").show();
            if (!title)
                title="Fragment play";
            title = title + " (" + _formatTime(debut) + " - " + _formatTime(fin) + ")";
            uiPlayer.find(".ui-dialog-fragment-title").text(title);
            this.minplayer.click();
        }
    };

    $.ui.player.prototype.videoObject = null;	
    $.ui.player.prototype.options.title = 'ADVENE PLAYER';
    $.ui.player.prototype.options.endFragmentBehaviour = "continue";
    $.ui.player.prototype.options.position = "right";
	

    
})(jQuery);

// Main advene plugin declaration.
// It defines the following methods:
// $(document).advene() or $(document).advene('init'): initialisation of the plugin
// element.advene('overlay'): hook the player call, and possibly add an overlay player over the screenshot
// element.advene('player', videoUrl, start, end): start the player at the given position
(function($) {

    // See http://docs.jquery.com/Plugins/Authoring#Plugin_Methods for the pattern used here.
    var methods = {
        'init': function(options) {
            // FIXME: pass appropriate options (player options, etc)
            var video_url = "";
            
            if (($("[target = 'video_player']").length == 0)) 
                // No video player link
                return;
            $("[target='video_player']").each( function() {
                var data = /(.+)#t=([.\d]+)?,([.\d]+)?/.exec($(this).attr('href'));
                
                if (data) { 
                    $(this).attr( { 'data-video-url': data[1], 
                                    'data-begin': data[2], 
                                    'data-end': data[3]
                                  });
                    if (!$(this).attr("title"))
                        $(this).attr("title", _formatTime(data[2]) + " - " + _formatTime(data[3]));
                    $(this).attr('href', '#');
                    if (video_url == "")
                        video_url = data[1];
                } 
                $(this).advene('overlay');
            });
            
            
            $("body").append("<div class='player_container' style='position:relative; overflow:visible; '>" + 
                             "<video style='overflow:visible; width:100%; height:auto; border:thick #00FF00; top:10; bottom:10;right:10;left:10; ' src='" + video_url + "'>" +
                             "</video></div>");

            playerOptions =  { title:'Advene main player', 
                               endFragmentBehaviour: 'continue',                               
                               transcriptHighlight: ($(".transcript").length > 0)
                             };
            if (options !== undefined)
                for (key in options)
                    playerOptions[key] = options[key];
            $('.player_container').player( playerOptions );
        },
        
        'overlay': function() {
            //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            /////////////////////////////////////////// SCREENSHOT WIDGET //////////////////////////////////////////////////////////////
            // L'outil ScreenshotOverlay définit le comportement des images vignettes dans le cadre de l'application. Il définit un certain nombre de traitements sur les objets image de la classe screenshot.
            // L'outil met les frères et soeurs, au sens DOM, de l'objet screenshot dans un conteneur CAPTION, le rendant tout le contenu disponible uniquement au survol de l'objet screenshot.
            // L'outil définit au dessous de l'objet screenshot les ancres permettant de lancer es lecteurs appropriés du fragment référencé.
	        var options = {
	            border_color : '#666',
	            overlay_color : '#000',
	            overlay_text_color : '#666'};
            
            
		        var fragmentTitle = $('.screenshot', this).siblings("strong:first").text();
            
            if ($(this).children('.screenshot').size() == 0)
            {
                // No screenshot. Simply trigger the appropriate action.
                $(this).click(function() {
                    $('.player_container').player('fragmentPlay', $(this).attr('data-begin'), $(this).attr('data-end'));
                    return false;
                });
                return false;
            }

	        $('.screenshot', this).siblings().wrapAll("<div class='caption'/>");
            
	        $(this).addClass('image-overlay');
            

		    $optionPlay=$('<div/>')
			    .attr("class","option-play")
			    .appendTo( $(this));

		    var  $option = $('<img/>')
			    .attr('src', './resources/HTML5/view_here.png')
			    .appendTo($optionPlay)
			    .click( function() {
			        node = $('.screenshot', this).parent();
			        $('.screenshot', this).hide();
			        $('.caption', this).hide();
			        $('.option-play', this).switchClass('option-play','option-play-off', 100);
			        $(this).parent().advene('player', node.attr('data-video-url'), node.attr('data-begin'), node.attr('data-end'));
			    });

		    option = $('<img/>')
			    .attr('src', './resources/HTML5/view_player.png')
			    .css('top', 30)
			    .click( function(event){
			        node = $('.screenshot', this).parent();
			        $('.player_container').player('fragmentPlay', node.attr('data-begin'), node.attr('data-end'), fragmentTitle);
			    })
			    .appendTo($optionPlay);


		    var image = new Image();
		    image.src = $('img', this).attr('src');
		    $(this).css({
			    width :$('img', this).css('width'),
			    height : $('img', this).css('height'),
			    borderColor : options.border_color});
		    $('img', this).attr({ title : '' });
            

		    var imageHeight = $('img', this).height();
		    var captionHeight = $('.caption', this).height();
            
		    $('.caption', this).css({
			    top: (options.always_show_overlay ? '0px' :  imageHeight + 'px'),
			    backgroundColor: options.overlay_color,
			    color : options.overlay_text_color
		    });
            
		    $(this).hover(function() {
                $('.caption', this).stop().animate( {
                    top: (imageHeight - captionHeight) + 'px'
                }, {
                    queue: false
                });
                $('.option-play', this).fadeIn(800);
            },
			              function() { 
                              $('.caption', this).stop().animate( {
                                  top: imageHeight + 'px'
                              }, {
                                  queue: false
                              });
                              $('.option-play', this).fadeOut(200);
		                  });
            
		    this.bind( "fragmentclose", function(event,parentC) {
			    $(parentC).find('.screenshot').show();
			    $(parentC).find('.caption').show();
			    $(parentC).find('.option-play-off').switchClass('option-play-off','option-play', 100);
			    this.die();
		    } );
	    },
        
        'player': function(videoURL, startx, endx) {
            ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            ///////////////////////////////////////// SAMPLE PLAYER WIDGET ////////////////////////////////////////////////////////
            // L'outil player définit un lecteur html5 video vignette. Il instancie un objet video() en lui définissant un conteneur vignette.
		    this.options = {
	            start_point: 0,
	            end_point: 0
	        };
	        this.options.start_point = startx;
	        this.options.end_point = endx;

		    var parentC = null;
		    return this.each(function() {
			    /**
			     * @type {!jQuery}
			     * @private
			     */
			    this.addClass('video-container');
			    this._videoContainer = null;
			    this._videoContainer = $('<div/>',
				                         {
					                         'class': ' ui-corner-all ui-video-container'
				                         }
			                            )
			        .css('height', $(this).css('height'))
			        .css('width', $(this).css('width'))
			        .css('background-color', 'black')
			        .css('padding', '0');

			    this._video = $('<video/>',
				                {
					                'class': ' ui-corner-all sampleContainer',
					                'src': videoURL
				                }
			                   )
			        .css('position', 'fixed')
			        .prependTo(this._videoContainer);

			    $(this._video).video({
                    'vignet':'true', 
                    'startPoint':this.options.start_point,
                    'endPoint':this.options.end_point,
                    'autoPlay':true
                });
			    parentC = $(this).parent();
			    parentC.append(this._videoContainer);
			    //destroy();
			    this._videoContainer
			        .css('height','100%')
			        .css('width','100%');

			    this.bind( "destroySamplePlayer", destroySamplePlayer );
		    });
		    function destroySamplePlayer() {
			    $(this._video).video("destroy");
			    this._video.remove();
			    this._videoContainer.empty();
			    this._videoContainer.remove();
			    this.removeClass('video-container');
			    parentC.find('.screenshot:first').trigger('fragmentclose',parentC);
			    this.unbind( "destroySamplePlayer", destroySamplePlayer );
		    }
	    }
    };

    $.fn.advene = function( method ) {
        // Method calling logic
        if ( methods[method] ) {
            return methods[ method ].apply( this, Array.prototype.slice.call( arguments, 1 ));
        } else if ( typeof method === 'object' || ! method ) {
            return methods.init.apply( this, arguments );
        } else {
            $.error( 'Method ' +  method + ' does not exist on jQuery.tooltip' );
        } 
  };
})(jQuery);
