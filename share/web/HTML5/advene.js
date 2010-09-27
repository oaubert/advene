/*
L'API consiste en quatre widgets principales permettant de définir des vignettes, players vignettes et players autonomes faisant appel aux services de html5 video
*/

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
        location: { 'left': 0, 'top': 0 }
	},
    
	_create: function() {
		var self = this;
        
	    //  	Paramètrage avec les options nécessaires et celles spécifiées lors de l'instanciation
		var videoOptions = {
			autoplay: self.options.autoPlay,
			controls: false,
			loop: self.options.loop,
			autobuffer: self.options.autoBuffer
		};
        
		/**
		 * @type {!Object}
		 * @private
		 */
		self._container = self.element.parent();
		if (self.options.vignet)
            self.options.fragmentPlay=true;
        
		/**
		 * @type {!Object}
		 * @private
		 */
		self._oldVideooptions = {};
        
		$.each( videoOptions , function( key, value) {
			if( value !== null ) {
				// webkit bug
				if( key == 'autoplay' && $.browser.webkit ) {
					value = false;
				}
				self._oldVideooptions[key] = self.element.attr( key );
				self.element.attr( key, value );
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
			if( self["_event_" + this] ) {
				self.element.bind(
					this + ".video",
					$.proxy(self["_event_" + this],self)
				);
			} else {
				self.element.bind(
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
		self._createControls();
		self._container.hover(
			$.proxy(self._showControls,self),
			$.proxy(self._hideControls,self)
		);
        
	    //  	Indicatif d'attente
		/**
		 * @type {!Object}
		 * @private
		 */
		self._waitingContainer = $('<div/>', {'class': 'ui-video-waiting-container'});

		/**
		 * @type {!Object}
		 * @private
		 */
		self._waiting = $('<div/>', {'class': 'ui-video-waiting'}).appendTo(self._waitingContainer);
        
		self._controls
			.fadeIn(500)
			.delay(100)
			.fadeOut(500);
        
		self._volumeSlider.slider('value', self.options.volume * 100);
        
		// webkit bug
		if( self.options.autoPlay && $.browser.webkit ) {
			self.play();
		}
	},
	// 	Fonction privée de création de contrôles
	_createControls: function() {
		var self = this;
		vigneText = '';
		if (self.options.vignet) {
            vigneText='-vign';
        }
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._controls = $('<div/>',
				           {
					           'class': ' ui-corner-all ui-video-control'+vigneText
				           }
			              )
			.prependTo(self._container);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._progressDiv = $('<div/>',
				              {
					              'class': 'ui-video-progress'
				              }
			                 )
			.appendTo(self._controls);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._currentProgressSpan = $('<span/>',
				                      {
					                      'class': 'ui-video-current-progress', 'text': '00:00'
				                      }
			                         )
			.appendTo(self._progressDiv);
        
		$('<span/>',
		  {
			  'html': '/',
			  'class': 'ui-video-progress-divider'
		  }
		 )
			.appendTo(self._progressDiv);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._durationSpan = $('<span/>',
				               {
					               'class': 'ui-video-length', 'text': '00:00'
				               }
			                  )
			.appendTo(self._progressDiv);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
        
		self._muteButton = $('<div/>',
				             {
					             'class': 'ui-icon ui-icon-volume-on ui-video-mute'+vigneText
				             }
			                )
			.appendTo(self._controls)
			.bind('click.video', $.proxy(self._mute,self));
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._playButton = $('<div/>',
				             {
					             'class': 'ui-icon ui-icon-play ui-video-play'+vigneText
				             }
			                )
			.appendTo(self._controls)
			.bind('click.video', $.proxy(self._togglePlayPause,self));
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._stopButton = $('<div/>',
				             {
					             'class': 'ui-icon ui-icon-stop ui-video-stop'+vigneText
				             }
			                )
			.appendTo(self._controls)
			.bind('click.video', $.proxy(self._stopfragmentplay,self))
			.bind('click.video', $.proxy(self._stop,self));
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._playLoopButton = $('<div/>',
				                 {
					                 'class': 'ui-icon ui-icon-arrowrefresh-1-s ui-video-playLoop'+vigneText
				                 }
			                    )
			.appendTo(self._controls)
			.bind('click.video', $.proxy(self._tooglePlayLoop,self));
        

		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._stopFragmentLoop = $('<div/>',
				                   {
					                   'class': 'ui-icon ui-icon-closethick ui-video-fragmentLoop'+vigneText
				                   }
			                      )
			.appendTo(self._controls)
			.hide()
			.bind('click.video', $.proxy(self._stopfragmentplay,self));
        
        
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._volumeSlider = $('<div/>',
				               {
					               'class': 'ui-video-volume-slider'+vigneText
				               }
			                  )
			.appendTo(self._controls)
			.slider({
				range: 'min',
				animate: true,
				stop: function( e, ui ) {
					ui.handle.blur();
				},
				slide: function( e, ui ) {
					self.volume.apply(self,[ui.value]);
					return true;
				}
			}
			       );
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._timeLinerSliderHover =  $('<div/>',
				                        {
					                        'class': 'ui-widget-content ui-corner-all ui-video-timeLiner-slider-hover'
				}
			                           )
			.hide();
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._timeLinerSlider = $('<div/>',
				                  {
					                  'class': 'ui-video-timeLiner-slider'+vigneText
				                  }
			                     )
			.appendTo(self._controls)
			.slider({
				range: 'min',
				animate: true,
				start: function( e, ui ) {
					if( self.element[0].readyState === HTMLMediaElement.HAVE_NOTHING ) {
						return false;
					} else {
						self._timeLinerSliderHover.fadeIn('fast');
						self._timeLinerHoverUpdate.apply(self,[ui.handle, ui.value]);
						return true;
					}
				},
				stop: function( e, ui ) {
                    
					ui.handle.blur();
					if( self._timeLinerSliderHover.is(':visible') ) {
						self._timeLinerSliderHover.fadeOut('fast');
					}
                    
					if( self.element[0].readyState === HTMLMediaElement.HAVE_NOTHING ) {
						return false;
					} else {
						self._currentProgressSpan.text(self._formatTime(self.element[0].duration * (ui.value/100)));
						return true;
					}
				},
				slide: function( e, ui ) {
					if( self.element[0].readyState === HTMLMediaElement.HAVE_NOTHING ) {
						return false;
					} else {
						self._timeLinerHoverUpdate.apply(self,[ui.handle, ui.value]);
						self.timeline.apply(self,[ui.value]);
						return true;
					}
				}
			}
			       );
        
		self._timeLinerSliderHover.appendTo(self._timeLinerSlider);
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._timeLinerSliderAbsoluteWidth = self._timeLinerSlider.width();
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._bufferStatus = $('<div/>',
				               {
					               'class': 'ui-video-buffer-status ui-corner-all'
				               }
			                  ).appendTo( self._timeLinerSlider );
        
		/**
		 * @type {!jQuery}
		 * @private
		 */
		self._stopFragmentButton = $('<div/>',
				                     {
					                     'class': 'ui-icon ui-icon-closethick ui-video-fragment-close'+vigneText
				                     }
			                        )
			.appendTo(self._controls)
			.bind('click.video', $.proxy(self._closeFragment,self));
	},
	/**
	 * @private
	 */
	_timeLinerHoverUpdate: function( elem, value ) {
		var self = this;
		var duration = self.element[0].duration;
        
		self._timeLinerSliderHover
			.text(self._formatTime(duration * (value/100)))
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
		var self = this;
		if( self.element[0].paused ) {
			self.play();
		} else {
			self.pause();
		}
	},
	/**
	 * @private
	 */
	_stop: function() {
		var self = this;
		self.stop();
	},
	_tooglePlayLoop: function() {
		var self = this;
		if (self.element[0].loop) { 
            self.element[0].loop=false;
		    self._playLoopButton.removeClass('ui-icon-arrowthickstop-1-e').addClass('ui-icon-arrowrefresh-1-s');
        } else {
            self.element[0].loop=true;
			self._playLoopButton.addClass('ui-icon-arrowthickstop-1-e').removeClass('ui-icon-arrowrefresh-1-s');
        }
	},
	/**
	 * @private
	 */
	_stopfragmentplay: function() {
		var self = this;
		self.options.fragmentPlay=false;
		self._stopFragmentLoop.hide();
		self._container.parent().find(".ui-dialog-fragment-title").hide();
		self._container.parent().find(".ui-dialog-fragment-title").text("Fragment PLAY");
	},
	/**
	 * @private
	 */
	_mute: function() {
		var self = this;
		var muted = self.element[0].muted = !self.element[0].muted;
		self._muteButton.toggleClass('ui-icon-volume-on', !muted).toggleClass('ui-icon-volume-off', muted);
	},
	/**
	 * @private
	 */
	_hideControls: function() {
		var self = this;
		self._controls
			.stop(true,true)
			.delay(100)
			.fadeOut(500);
	},
	/**
	 * @private
	 */
	_showControls: function(){
		var self = this;
		self._controls
			.stop(true,true)
        
			.fadeIn(500);
	},
	/**
	 * @private
	 */
	_hideWaiting: function(){
		var self = this;
		if( self._waitingId ) {
			clearInterval( self._waitingId );
			self._waitingId = null;
			self._waitingContainer.fadeOut('fast').remove();
		}
	},
	/**
	 * @private
	 */
	_showWaiting: function(){
		var self = this;
		if( ! self._waitingId ) {
			self._waiting.css('left', 0);
			self._waitingContainer
				.appendTo(self._container)
				.position({
					'my': 'center',
					'at': 'center',
					'of': self.element,
					'collision': 'none'
				}
				         ).fadeIn('fast');
			var waitingWidth = self._waiting.width();
			var _waitingContainerWidth = self._waitingContainer.width();
			self._waitingId = setInterval(function() {
				var cur_left = Math.abs(self._waiting.position().left);
                
				self._waiting.css({'left': -((cur_left + _waitingContainerWidth) % waitingWidth) });
                
			}, 50);
		}
	},

	/**
	 * @private
	 */
	_closeFragment: function() {
		var self = this;
		self._container.parent().find('.video-container:first').trigger("destroySamplePlayer");
        
	},
    
	/**
	 * @private
	 */
	_formatTime: function( seconds ) {
		var h = parseInt(seconds / 3660);
		var m = parseInt((seconds / 60)-(h*60));
		var s = parseInt(seconds % 60);
		var sp = s >= 10 ? '' : '0';
		var mp = m >= 10 ? '' : '0';
		var hp = h >= 10 ? '' : '0';
		return hp + h + ':' + mp + m + ":" + sp + s;
	},
    
    
	// Events
	/**
	 * @private
	 */
	_event_progress: function(e) {
		var self = this;
		var lengthComputable = e.originalEvent.lengthComputable,
		loaded = e.originalEvent.loaded,
		total = e.originalEvent.total;
        
		if( lengthComputable ) {
			var fraction = Math.max(Math.min(loaded / total,1),0);
            
			this._bufferStatus.width(Math.max(fraction * self._timeLinerSliderAbsoluteWidth));
		}
        
	},
	/**
	 * @private
	 */
	_event_seeked: function() {
		var self = this;
		self._hideWaiting();
	},
	/**
	 * @private
	 */
	_event_canplay: function() {
		var self = this;
		self._hideWaiting();
	},
	/**
	 * @private
	 */
	_event_loadstart: function() {
		var self = this;
		self._showWaiting();
	},
	/**
	 * @private
	 */
	_event_durationchange: function() {
		var self = this;
		self._showWaiting();
	},
	/**
	 * @private
	 */
	_event_seeking: function() {
		var self = this;
		self._showWaiting();
	},
	/**
	 * @private
	 */
	_event_waiting: function() {
		var self = this;
		self._showWaiting();
	},
	/**
	 * @private
	 */
	_event_loadedmetadata: function() {
		var self = this;
		self._durationSpan.text(self._formatTime(self.element[0].duration));
	},
	/**
	 * @private
	 */
	_event_play: function() {
		var self = this;
		self._playButton.addClass('ui-icon-pause').removeClass('ui-icon-play');
	},
	/**
	 * @private
	 */
	_event_pause: function() {
		var self = this;
		self._playButton.removeClass('ui-icon-pause').addClass('ui-icon-play');
	},

	/**
	 * @private
	 */
	_event_timeupdate: function() {
		var self = this;
		if( ! self.element[0].seeking ) {
			var duration = self.element[0].duration;
			var currentTime = self.element[0].currentTime;

			if (((currentTime > self.options.endPoint) || (currentTime<self.options.startPoint)) && (self.options.fragmentPlay))
			{
				switch(self.options.endFragmentBehaviour)
				{
				case "continue":
					self._stopfragmentplay();
					break;
				case "pause":
					self._stopfragmentplay();
					self.pause();
					break;
				case "stop":
					self._stopfragmentplay();
					self.stop();
					break;
				default: // LOOP
					self.element[0].currentTime = self.options.startPoint;
				}
				return;
			}
            
			self._timeLinerSlider.slider(
				'value',
				[(currentTime / (self.element[0].duration)) * 100]
			);
            
			self._durationSpan.text(self._formatTime(self.element[0].duration));
			self._currentProgressSpan.text(self._formatTime(currentTime));
            
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
		var self = this;
        alert('_event_resize');
		self._controls.position({
			'my': 'bottom',
			'at': 'bottom',
			'of': self.element,
			'offset': '0 -10',
			'collision': 'none'
		}
			                   );
		self._container.width( self.element.outerWidth(true) );
		self._container.height( self.element.outerHeight(true) );
	},
    
	// User functions
	getIntrinsicWidth: function() {
		var self = this;
        self._wait(500);
		return (self.element[0].videoWidth);
        
	},
	getIntrinsicHeight: function() {
		var self = this;
		return (self.element[0].videoHeight);
	},
	play: function() {
		var self = this;
		self.element[0].play();
	},
	pause: function() {
		var self = this;
		self.element[0].pause();
	},
	stop: function() {
		var self = this;
		this.fragmentLoop = false;
		self.element[0].currentTime = 0;
		self.element[0].pause();
		self._timeLinerSlider.slider('value', 0);
		self._currentProgressSpan.text(self._formatTime(0));


	},
	mute: function() {
		var self = this;
		self.element[0].muted = true;
	},
	unmute: function() {
		var self = this;
		self.element[0].muted = false;
	},
	rewind: function() {
		var self = this;
		self.element[0].playbackRate -= 2;
	},
	forward: function() {
		var self = this;
		self.element[0].playbackRate += 2;
	},
	volume: function(vol) {
		var self = this;
		self.element[0].volume = Math.max(Math.min(parseInt(vol) / 100, 1), 0);
	},
	timeline: function(pos){
		var self = this;
		var duration= self.element[0].duration;
		var pos = Math.max(Math.min(parseInt(pos) / 100, 1), 0);
		self.element[0].currentTime = duration * pos;
	},
	setPlayingTime: function(pos){
		var self = this;
		try{
			self.element[0].currentTime = pos;
			self.play();
		}
		catch(e){}
        
	},
	fragmentPlay: function(debut, fin, endFragBehav) {
		var self = this;
        self.element[0].load();
		setTimeout(function() {            
			self.options.endPoint = fin > 0 ? fin:self.element[0].duration;
			self.options.startPoint = debut;
			self.options.fragmentPlay = true;
			self.options.endFragmentBehaviour = endFragBehav;
			self._stopFragmentLoop.show();
			self.setPlayingTime(debut);
		}, 500);

	},

	// The destroyer
	destroy: function() {
		var self = this;
		$.each( self._oldVideooptions , function( key, value) {
			self.element.attr( key, value );
		}
			  );
        
		self._controls.remove();
		self.element.unwrap();
		self.element.unbind( ".video" );
		$.Widget.prototype.destroy.apply(self, arguments); // default destroy
	}
});

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////// SCREENSHOT WIDGET //////////////////////////////////////////////////////////////
// L'outil ScreenshotOverlay définit le comportement des images vignettes dans le cadre de l'application. Il définit un certain nombre de traitements sur les objets image de la classe screenshot.
// L'outil met les frères et soeurs, au sens DOM, de l'objet screenshot dans un conteneur CAPTION, le rendant tout le contenu disponible uniquement au survol de l'objet screenshot.
// L'outil définit au dessous de l'objet screenshot les ancres permettant de lancer es lecteurs appropriés du fragment référencé.

(function($) {
    $.fn.ScreenshotOverlay = function() {
	    var options = {
	        border_color : '#666',
	        overlay_color : '#000',
	        overlay_text_color : '#666'};
        
        
	    var self = this;
	    var fragmentTitle = $('.screenshot', this).siblings("strong:first").text();
        
        if ($(this).children('.screenshot').size() == 0)
        {
            $(this).attr('href','#');
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
			.appendTo( $(self));

		var  $option = $('<img/>')
			.attr('src', './resources/HTML5/view_here.png')
			.appendTo($optionPlay)
			.click( function() {
			    node = $('.screenshot', self).parent();
			    $('.screenshot', self).hide();
			    $('.caption', self).hide();
			    $('.option-play', self).switchClass('option-play','option-play-off', 100);
			    $(this).parent().SamplePlayer(node.attr('data-video-url'), node.attr('data-begin'), node.attr('data-end'));
			});

		option = $('<img/>')
			.attr('src', './resources/HTML5/view_player.png')
			.css('top', 30)
			.click( function(event){
			    node = $('.screenshot', self).parent();
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
        
		self.bind( "fragmentclose", function(event,parentC) {
			$(parentC).find('.screenshot').show();
			$(parentC).find('.caption').show();
			$(parentC).find('.option-play-off').switchClass('option-play-off','option-play', 100);
			self.die();
		} );
	};
    
})(jQuery);

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////// SAMPLE PLAYER WIDGET ////////////////////////////////////////////////////////
// L'outil SamplePlayer définit un lecteur html5 video vignette. Il instancie un objet video() en lui définissant un conteneur vignette.
(function($) {
    $.fn.SamplePlayer = function(videoURL, startx, endx) {
	    var self = this;
	    self.options = {
	        start_point: 0,
	        end_point: 0
	    };
	    self.options.start_point = startx;
	    self.options.end_point = endx;

		var parentC = null;
		return this.each(function() {
			/**
			 * @type {!jQuery}
			 * @private
			 */
			self.addClass('video-container');
			self._videoContainer = null;
			self._videoContainer = $('<div/>',
				                     {
					                     'class': ' ui-corner-all ui-video-container'
				                     }
			                        )
			    .css('height', $(self).css('height'))
			    .css('width', $(self).css('width'))
			    .css('background-color', 'black')
			    .css('padding', '0');

			self._video = $('<video/>',
				            {
					            'class': ' ui-corner-all sampleContainer',
					            'src': videoURL
				            }
			               )
			    .css('position','absolute')
			    .prependTo(self._videoContainer);

			$(self._video).video({
                'vignet':'true', 
                'startPoint':self.options.start_point,
                'endPoint':self.options.end_point,
                'autoPlay':true
            });
			parentC = $(self).parent();
			parentC.append(self._videoContainer);
			//destroy();
			self._videoContainer
			    .css('height','100%')
			    .css('width','100%');

			self.bind( "destroySamplePlayer", destroySamplePlayer );
		});
		function destroySamplePlayer() {
			$(self._video).video("destroy");
			self._video.remove();
			self._videoContainer.empty();
			self._videoContainer.remove();
			self.removeClass('video-container');
			parentC.find('.screenshot:first').trigger('fragmentclose',parentC);
			self.unbind( "destroySamplePlayer", destroySamplePlayer );
		};
	};


})(jQuery);

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////// MAIN PLAYER WIDGET ////////////////////////////////////////////////////////////
// L'outil player définit un lecteur html5 video. Il instancie un objet video() en lui définissant un conteneur indépendant. Le conteneur lui-même est dérivé de ui.dialog de jquery auquel un certain nombre de fonctions ont été greffées
// pour le compte de l'application
(function($) {
    player=$.extend({}, $.ui.dialog.prototype);
    $.widget("ui.player", $.ui.dialog, player);
    var _init = $.ui.player.prototype._init;

    $.ui.player.prototype._init = function() {
        var self = this;
        var options = self.options;
        var videoObject;

        options.closeOnEscape = false;
        _init.apply(this, arguments);
        uiPlayer=self.uiDialog;

        ////////////// CREATE MINIMIZED ICON FOR PLAYER
        self.minplayer=$('<img/>',
				         {
					         'class': ' ui-corner-all player_minimized',
					         'src': './resources/HTML5/maximized.png',
					         'title': self.options.title+' Click to restore'
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
				self.uiDialog.show();
				//('.player_container').player('open');
				//self.minplayer.css('top','0');
				self.minplayer.hide("transfer", options, 1000, function(){} );
				self.minplayer.hide();
				return false;
			})
        
        ///////////////////////////////////////////////////////
        if (self.options.sticky) {
            uiPlayer.css('position', 'fixed')
        };
        
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
        }


        uiPlayer
	        .bind('dragstop', function(event, ui) {
	            if (self.options.sticky)
	                storeLocation(ui.position.left,
	                              ui.position.top);
	        })
	        .bind('resizestart', function(event, ui) {
	            if (self.options.sticky)
	                storeLocation(ui.position.left - $
	                              (window).scrollLeft(),
	                              ui.position.top - $(window).scrollTop
	                              ());
	        })
	        .bind('resizestop', function(event, ui) {
	            if (self.options.sticky) {
	                uiPlayer.css({
	                    'position': 'fixed',
	                    'left': self.options.location.left,
	                    'top': self.options.location.top
	                });
	            };

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

        function storeLocation(_left, _top) {
            self.options.location = { 
                left: _left,
                top: _top 
            };
        };
        
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
                self.uiDialog.hide();
                self.minplayer.show();
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
			    self.uiDialog.draggable('destroy');
			    self.uiDialog.find('.ui-dialog-titlebar-nofixonscreen ',this).show();
			    return false;
		    })
		    .appendTo(uiPlayerTitlebar);
        
	    uiPlayerTitlebarFixonScreenText = (this.uiPlayerTitlebarFixonScreenText = $('<span/>'))
		    .addClass('ui-icon ' +'ui-icon-pin-s')
		    .text("Fix On Screen")
		    .attr('title','Fix Player position')
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
			self.uiDialog.draggable();
			self.uiDialog.find('.ui-dialog-titlebar-fixonscreen ').show();
			return false;
		})
		    .appendTo(uiPlayerTitlebar)
		    .hide();
        
	    uiPlayerTitlebarNoFixonScreenText = (this.uiPlayerTitlebarNoFixonScreenText = $('<span/>'))
		    .addClass('ui-icon ' +'ui-icon-pin-w')
		    .text('options')
		    .attr('title','Stop Fixing Player position')
		    .appendTo(uiPlayerTitlebarNoFixonScreen);
        
        // 	Fonction de fixation sur écran --> le player est affiché à un endroit et ne bouge pas avec défilement de la page
	    uiPlayerTitlebarStickonWindow = $('<a href="#"/>')
		    .addClass('ui-dialog-titlebar-stickonwindow ' +'ui-corner-all')
		    .attr('role', 'button')
		    .hover(function() {$(this).addClass('ui-state-hover');},
			       function() {$(this).removeClass('ui-state-hover');}
			      )
		    .focus(function() {$(this).addClass('ui-state-focus');})
		    .blur(function() {$(this).removeClass('ui-state-focus');})
		    .mousedown(function(ev) {
			    ev.stopPropagation();
		    })
		    .click(function(event) {
			    $(this).hide();
			    self.options.sticky=true;
			    self.uiDialog.find('.ui-dialog-titlebar-nostickonwindow ').show();
			    return false;
                
		    })
		    .appendTo(uiPlayerTitlebar);
        
        // 	Fonction de fixation sur écran --> le player est incrusté à la page de la manère classique
	    uiPlayerTitlebarNoStickonWindow = $('<a href="#"/>')
		    .addClass('ui-dialog-titlebar-nostickonwindow ' +'ui-corner-all')
		    .attr('role', 'button')
		    .hover(function() {$(this).addClass('ui-state-hover');},
			       function() {$(this).removeClass('ui-state-hover');}
			      )
		    .focus(function() {$(this).addClass('ui-state-focus');})
		    .blur(function() {$(this).removeClass('ui-state-focus');})
		    .mousedown(function(ev) {
			    ev.stopPropagation();
		    })
		    .click(function(event) {
			    $(this).hide();
			    self.options.sticky=false;
			    self.uiDialog.find('.ui-dialog-titlebar-stickonwindow').show();
			    return false;
		    })
		    .appendTo(uiPlayerTitlebar)
		    .hide();
        
        //////////////////////////////////////////////
        self.fragmentPlay = function(debut, fin, title, endFragBehav) {
            videoObject.video('fragmentPlay', debut, fin, self.options.endFragmentBehaviour);
            uiPlayer.find(".ui-dialog-fragment-title").show();
            if (!title)
                title="Fragment PLAY";
            title = title + " (" + _formatTime(debut) + " - " + _formatTime(fin) + ")";
            uiPlayer.find(".ui-dialog-fragment-title").text(title);
            self.minplayer.click();
        }
    };

    // FIXME: duplicated code. To factorize.
    self._formatTime = function( seconds ) {
	    var h = parseInt(seconds / 3660);
	    var m = parseInt((seconds / 60) - (h * 60));
	    var s = parseInt(seconds % 60);
	    var sp = s >= 10 ? '' : '0';
	    var mp = m >= 10 ? '' : '0';
	    var hp = h >= 10 ? '' : '0';
	    return hp + h + ':' + mp + m + ":" + sp + s;
    },
    
    $.ui.player.prototype.videoObject = null;
    $.ui.player.prototype.options.sticky = true;
    $.ui.player.prototype.options.title = 'ADVENE PLAYER';
    $.ui.player.prototype.options.endFragmentBehaviour = "continue";
    $.ui.player.prototype.options.position = "right";
    
})(jQuery);

/* Initialisation code */
(function($) {
    $.fn.AdvenePlayerInit = function() {
        // FIXME: pass appropriate options (player options, etc)
        var video_url = "";

        if (($("[target = 'video_player']").length == 0)) 
            // No video player link
            return;
        $("[target='video_player']").each( function() {
            var data = /(.+)#t=(\d+)?,(\d+)?/.exec($(this).attr('href'));

            if (data) { 
                $(this).attr( { 'data-video-url': data[1], 
                                'data-begin': data[2], 
                                'data-end': data[3]
                              });
                if (video_url == "")
                    video_url = data[1];
            } 
            $(this).removeAttr('href');
            $(this).ScreenshotOverlay();
        });

        $("body").append("<div class='player_container' style='position:fixed; overflow:visible; '>" + 
                         "<video style='overflow:visible; width:100%; height:auto; border:thick #00FF00; top:10; bottom:10;right:10;left:10; ' src='" + video_url + "'>" +
                         "</video></div>");
        $('.player_container').player( { title:'ADVENE MAIN PLAYER', 
                                         endFragmentBehaviour: 'continue'} );

    }
})(jQuery)

