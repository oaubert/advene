/*
  The Advene HTML API defines 2 widgets (ui.player and ui.video) and 3 methods: init(), overlay(), player()

  2 behaviour options can be controlled (for the moment) by having an element (typically the document body) define a css class:
  - highlightRelated -> highlight related .transcript elements (i.e. .transcript elements whose fragments intersect)
  - transcriptFollow -> have the video follow .transcript elements(i.e. when the end of a .transcript element is reached, go to the begin time of the following (DOM-wise) .transcript element)
 */

_formatTime = function( seconds ) {
    var h = parseInt(seconds / 3660);
    var m = parseInt((seconds / 60)-(h*60));
    var s = Number(seconds % 60).toPrecision(3);
    // 0-padding
    var hp = h >= 10 ? '' : '0';
    var mp = m >= 10 ? '' : '0';
    var sp = s >= 10 ? '' : '0';
    return hp + h + ':' + mp + m + ":" + sp + s;
};


// L'outil video prend en charge les spécifications html5 video pour les besoins de l'API. Lors d'une instanciation d'une balise video en une instance video(), les options suivantes peuvent être incluses:
// ** Standard options
//  - VideoURL
//  - autoplay: automatically start playing
//  - loop
//  - autoBuffer
//  - volume
// ** Specific options
//  - overlay: indicates whether the player is overlayed over a screenshot, or it is an autonomous player
//  - fragmentPlay: indicate whether we are playing a fragment (with begin and end times). On a overlay=true ---> fragmentPlay=true
//  - startPoint et endpoint: begin and end of the fragment or the video
//  - endFragmentBehaviour: loop, pause, stop, continue.
$.widget("ui.video", {
    // default options
    options: {
        VideoURL: "",
        autoPlay: false,
        loop: false,
        autoBuffer: true,
        volume: .25,
        overlay: false,
        fragmentPlay: false,
        startPoint: 0,
        endPoint: 0,
        endFragmentBehaviour: "continue",
        transcriptHighlight: true,
        // Follow the transcription (dynamic montage)
        transcriptFollow: false,
        // Only 1 player at a time
        singletonPlayer: true,
        location: { 'left': 0, 'top': 0 }
    },

    _create: function() {
        var self = this;

        // Update self.options
        self.options.transcriptHighlight = ($(".transcript", document).length > 0);
        self.options.transcriptFollow = ($(".transcriptFollow", document).length > 0);

        var videoOptions = {
            autoplay: self.options.autoPlay,
            controls: false,
            loop: self.options.loop,
            autobuffer: self.options.autoBuffer
        };

        self._container = self.element.parent();
        if (self.options.overlay)
            self.options.fragmentPlay = true;

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

        //  Video playback events
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
            "loadeddata",
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
            "click",
            "keydown",
            "mouseover"
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

        //  Control bar instanciation
        self._createControls();
        self._container.hover(
            $.proxy(self._showControls, self),
            $.proxy(self._hideControls, self)
        );

        self._waitingContainer = $('<div/>', {'class': 'ui-corner-all ui-widget-content ui-video-waiting-container'});
        self._waiting = $('<div/>', {'class': 'ui-video-waiting'}).appendTo(self._waitingContainer);
        self._waiting.text("Loading...");
        self._controls
            .fadeIn(500)
            .delay(100)
            .fadeOut(500);

        self.element[0].volume = 0.25;
        self._volumeSlider.slider('value',parseInt(self.element[0].volume * 100));

        // webkit bug
        if( self.options.autoPlay && $.browser.webkit ) {
            self.play();
        }
    },
    //  Controls creation
    _createControls: function() {
        var self = this;

        self._controls = $('<div/>')
            .addClass(self.options.overlay ? 'ui-corner-all ui-video-control-vign' : 'ui-corner-all ui-video-control')
            .prependTo(self._container);

        self._progressDiv = $('<div/>')
            .addClass(self.options.overlay ? 'ui-corner-all  ui-video-progress-vign' : 'ui-corner-all  ui-video-progress')
            .appendTo(self._controls)
            .hover(
                function() {
                    $(this).effect("highlight");
                },
                function() {
                }
            );

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

        self._durationSpan = $('<span/>',
                               {
                                   'class': 'ui-video-length', 'text': '00:00'
                               }
                              )
            .appendTo(self._progressDiv);

        self._muteButton = $('<div/>')
            .addClass(self.options.overlay ? 'ui-icon ui-icon-volume-on ui-video-mute-vign' : 'ui-video-mute')
            .appendTo(self._controls)
            .bind('click.video', $.proxy(self._mute, self));

        self._playButton = $('<div/>')
            .addClass(self.options.overlay ? 'ui-icon ui-icon-play ui-video-play-vign' : 'ui-video-play')
            .appendTo(self._controls)
            .bind('click.video', $.proxy(self._togglePlayPause, self));

        self._stopButton = $('<div/>')
            .addClass(self.options.overlay ? 'ui-icon ui-icon-stop ui-video-stop-vign' : 'ui-video-stop')
            .appendTo(self._controls)
            .bind('click.video', $.proxy(self._stopfragmentplay, self))
            .bind('click.video', $.proxy(self._stop, self));

        self._playLoopButton = $('<div/>')
            .appendTo(self._controls)
            .addClass(self.options.overlay ? 'ui-icon ui-icon-arrowrefresh-1-s ui-video-playLoop-vign' : 'ui-video-playLoop')
            .bind('click.video', $.proxy(self._tooglePlayLoop, self));

        self._stopFragmentLoop = $('<div/>')
            .addClass(self.options.overlay ? 'ui-icon ui-icon-closethick ui-video-fragmentLoop-vign' : 'ui-video-fragmentLoop')
            .appendTo(self._controls)
            .hide()
            .bind('click.video', $.proxy(self._stopfragmentplay, self));

        self._volumeSlider = $('<div/>')
            .addClass(self.options.overlay ? 'ui-video-volume-slider-vign' : 'ui-video-volume-slider')
            .appendTo(self._controls)
            .slider({
                range: 'min',
                animate: true,
                stop: function( e, ui ) {
                    ui.handle.blur();
                },
                slide: function( e, ui ) {
                    self.volume.apply(self, [ui.value]);
                    return true;
                }
            }
                   );

        self._timeLinerSliderHover =  $('<div/>',
                                        {
                                            'class': 'ui-widget-content ui-corner-all ui-video-timeLiner-slider-hover'
                                        }
                                       )
            .hide();

        self._timeLinerSlider = $('<div/>')
            .addClass(self.options.overlay ? 'ui-video-timeLiner-slider-vign' : 'ui-video-timeLiner-slider')
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
                        self._currentProgressSpan.text(_formatTime(self.element[0].duration * (ui.value/100)));
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

        self._timeLinerSliderAbsoluteWidth = self._timeLinerSlider.width();

        self._bufferStatus = $('<div/>',
                               {
                                   'class': 'ui-video-buffer-status ui-corner-all'
                               }
                              ).appendTo( self._timeLinerSlider );

        self._stopFragmentButton = $('<div/>')
            .addClass(self.options.overlay ? 'ui-icon ui-icon-closethick ui-video-fragment-close-vign' : 'ui-icon ui-icon-closethick ui-video-fragment-close')
            .appendTo(self._controls)
            .bind('click.video', $.proxy(self._closeFragment,self));
    },
    _timeLinerHoverUpdate: function( elem, value ) {
        var self = this;
        var duration = self.element[0].duration;

        self._timeLinerSliderHover
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
    _togglePlayPause: function() {
        var self = this;
        if( self.element[0].paused ) {
            self.play();
        } else {
            self.pause();
        }
    },
    _stop: function() {
        var self = this;
        self.stop();
    },
    _tooglePlayLoop: function() {
        var self = this;
        if (self.element[0].loop) {
            self.element[0].loop=false;
            self._playLoopButton.removeClass('ui-video-noplayLoop').addClass('ui-video-playLoop');
        } else {
            self.element[0].loop=true;
            self._playLoopButton.addClass('ui-video-noplayLoop').removeClass('ui-video-playLoop');
        }
    },
    _stopfragmentplay: function() {
        var self = this;
        self.options.fragmentPlay=false;
        self._stopFragmentLoop.hide();
        self._container.parent().find(".ui-dialog-fragment-title").hide();
        self._container.parent().find(".ui-dialog-fragment-title").text("Fragment play");
    },
    _mute: function() {
        var self = this;
        var muted = self.element[0].muted = !self.element[0].muted;
        self._muteButton
            .toggleClass(self.options.overlay ? 'ui-icon-volume-on' : 'ui-video-mute', !muted)
            .toggleClass(self.options.overlay ? 'ui-icon-volume-off' : 'ui-video-unmute', muted);
    },
    _hideControls: function() {
        var self = this;
        self._controls
            .stop(true,true)
            .delay(100)
            .fadeOut(500);
    },
    _showControls: function(){
        var self = this;
        self._controls
            .stop(true, true)
            .fadeIn(500);
    },
    _hideWaiting: function(){
        var self = this;
        if( self._waitingId ) {

            self._waitingId = false;
            self._waitingContainer
                    .fadeOut('fast')
                    .remove();
        }
    },
    _showWaiting: function(msg){
        var self = this;
        self._waiting.text(msg);
        self._waiting.css('width', self._container.width() - 12);
        self._waiting.css('width', self._waitingContainer.width() - 12);
        if( ! self._waitingId ) {
            self._waiting.css('left', 0);
            self._waitingContainer
                .appendTo(self._container)
                .css('left', 5)
                .css('right', 5)
                .css('top',  (self._container.height()- self._waiting.height())/3)
                .fadeIn('slow');
            self._waitingId=true;
        }
    },
    _closeFragment: function() {
        var self = this;
        self._container.parent().find('.video-container:first').trigger("destroySamplePlayer");
    },

    // Event handling
    _event_progress: function(e) {
        var self = this;

        // Cf https://github.com/aFarkas/jMediaelement/blob/1.1.3/src/mm.base-api.js#L312 for more complete implementation
        if (e.target.buffered && e.target.buffered.length) {
            // current w3 spec using buffered TimeRange
            // FIXME: we only consider the 1st buffer.
            fraction = e.target.buffered.end(0) / e.target.duration;
            this._bufferStatus.width(fraction * self._timeLinerSliderAbsoluteWidth);
            self._waiting.text("Loaded " + Math.floor(fraction * 100) + "%...");
        } else if (e.originalEvent && 'lengthComputable' in e.originalEvent && e.originalEvent.loaded) {
            // Firefox/old webkits
            var lengthComputable = e.originalEvent.lengthComputable,
                loaded = e.originalEvent.loaded,
                total = e.originalEvent.total;
            if( total && lengthComputable ) {
                var fraction = Math.max(Math.min(loaded / total, 1), 0);

                this._bufferStatus.width(fraction * self._timeLinerSliderAbsoluteWidth);
                self._waiting.text("Loaded " + Math.floor(fraction*100) + "%...");
            }
            else
            {
                self._waiting.text("Loaded " + Math.floor(loaded / 1024) + " Kbytes...");
            }
        }
    },
    _event_seeked: function() {
        var self = this;
        self._hideWaiting();
    },
    _event_canplay: function() {
        var self = this;
        self._hideWaiting();
    },
    _event_loadeddata: function() {
        var self = this;
        self._hideWaiting();
    },
    _event_canplaythrough: function() {
        var self = this;
        self._hideWaiting();
    },
    _event_loadstart: function() {
        var self = this;
        self._showWaiting("Loading...");
    },
    _event_durationchange: function() {
        var self = this;
        self._showWaiting("Loading...");
    },
    _event_seeking: function() {
        var self = this;
        self._showWaiting("Loading...");
    },
    _event_waiting: function() {
        var self = this;
        self._showWaiting("Loading...");
    },
    _event_loadedmetadata: function() {
        var self = this;
        self._durationSpan.text(_formatTime(self.element[0].duration));
    },
    _event_play: function() {
        var self = this;

        // Pause all other players
        if (self.options.singletonPlayer)
            $("video", $(document)).each( function() { if (this !== self.element[0] && !this.paused && !this.ended) this.pause(); } );
        self._playButton.addClass(self.options.overlay ? 'ui-icon-pause' : 'ui-video-pause').removeClass(self.options.overlay ? 'ui-icon-play' : 'ui-video-play');
    },
    _event_pause: function() {
        var self = this;
        self._playButton.removeClass(self.options.overlay ? 'ui-icon-pause' : 'ui-video-pause').addClass(self.options.overlay ? 'ui-icon-play' : 'ui-video-play');
    },
    _event_timeupdate: function() {
        var self = this;
        if( ! self.element[0].seeking ) {
            var duration = self.element[0].duration;
            var currentTime = self.element[0].currentTime;

            if( self._waitingId ) {
                // Should not be "Waiting"
                self._hideWaiting();
            }

            if (self.options.fragmentPlay) {
                if (currentTime < self.options.startPoint) {
                    self.element[0].currentTime = self.options.startPoint;
                } else if (currentTime > self.options.endPoint) {
                    switch(self.options.endFragmentBehaviour) {
                    case "continue":
                        if (self.options.overlay) {
                            self.element[0].currentTime = self.options.startPoint;
                            break;
                        }
                        else {
                            self._stopfragmentplay();
                            break;
                        }
                    case "pause":
                        self._stopfragmentplay();
                        self.pause();
                        break;
                    case "stop":
                        self._stopfragmentplay();
                        self.stop();
                        break;
                    default: // 'loop' is the default behaviour
                        self.setPlayingTime(self.options.startPoint);
                    }
                }
            }

            // Highlight/unhighlight elements by using the .activeTranscript class
            if (self.options.transcriptHighlight)
                $(".transcript[data-begin]", $(document)).each( function() {
                    if ($(this).hasClass('activeTranscript')) {
                        if ((currentTime < $(this).attr('data-begin') || currentTime > $(this).attr('data-end'))) {
                            $(this).removeClass('activeTranscript');
                            if (self.options.transcriptFollow) {
                                // Get the next transcript node
                                next = $(this).next().find(".transcript");
                                if (! next.length)
                                    // The element could be inside a container.
                                    // FIXME: how many container levels should we take into account?
                                    next = $(this).parent().next().find(".transcript");
                                if (next.length) {
                                    // A next node has been found. Go to it
                                    t = next[0].getAttribute('data-begin');
                                    // Only follow the timecode if new
                                    // time is sufficiently
                                    // different. This avoids infinite
                                    // looping when adjacent
                                    // annotations share the same
                                    // begin/end time
                                    if (Math.abs(t - $(this).attr('data-end')) > .5)
                                        setTimeout(function() {
                                            // FIXME: check data-video-url for multi-video case
                                            self.setPlayingTime(t);
                                        }, 200);
                                } else {
                                    self.pause();
                                }
                            }
                        }
                    } else {
                        if ($(this).attr('data-begin') <= self.element[0].currentTime && self.element[0].currentTime <= $(this).attr('data-end')) {
                                $(this).addClass('activeTranscript');
                            }
                    }
                });

            self._timeLinerSlider.slider(
                'value',
                [(currentTime / (self.element[0].duration)) * 100]
            );

            self._durationSpan.text(_formatTime(self.element[0].duration));
            self._currentProgressSpan.text(_formatTime(currentTime));

        }
    },
    _event_resize: function() {
        var self = this;
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

    _event_click: function() {
        var self = this;
        this._togglePlayPause();
    },

    _event_error: function(e) {
        var self = this;
        var textError = "Playback Error";

        if (! e.target.error)
            return;

        switch (e.target.error.code) {
        case e.target.error.MEDIA_ERR_ABORTED:
            textError='You aborted the video playback.';
            break;
        case e.target.error.MEDIA_ERR_NETWORK:
            textError='A network error caused the video download to fail part-way.';
            break;
        case e.target.error.MEDIA_ERR_DECODE:
            textError='The video playback was aborted due to a corruption problem or because the video used features your browser did not support.';
            break;
        case e.target.error.MEDIA_ERR_SRC_NOT_SUPPORTED:
            textError='The video could not be loaded, either because the server or network failed or because the format is not supported.';
            break;
        default:
            textError=textError+'An unknown error occurred.';
            break;
        }


        self._showWaiting(textError);



    },

    _event_volumechange: function() {
        var self = this;
        self._volumeSlider.slider('value', parseInt(self.element[0].volume * 100));
    },

    _event_mouseover: function() {
        var self = this;
        $(self).focus();

    },

    _event_keydown: function(e) {
        var self = this;
        var handled_event = true;
        if (!e)
            e = window.event;

        switch (e.keyCode){
            case 32:  // Space
                self._togglePlayPause();
                break;
            case 38: // up-arrow
                self.volume.apply(self, [parseInt(self.element[0].volume * 100 + 10)]);
                break;
            case 40: // down-arrow
                self.volume.apply(self, [parseInt(self.element[0].volume * 100 - 10)]);
                break;
            case 36: // Home
                self.setPlayingTime(0);
                break;
            case 37: // left-arrow (<--)
                self.setPlayingTime(self.element[0].currentTime - 60);
                break;
            case 39: // right-arrow (-->)
                self.setPlayingTime(self.element[0].currentTime + 60);
                break;
            case 27: // Escape
                self.stop();
                break;
            default:
                handled_event = false;
        }
        if (! handled_event) {
            // handled event, stop propagating it!
            e.cancelBubble = true;
            if (e.preventDefault) e.preventDefault();
            if (e.stopPropagation) e.stopPropagation();
            return false;
        } else {
            return true;
        }
     },

    _wait: function(t) {
        var date = new Date();
        var curDate = null;
        do {
            curDate = new Date();
        } while (curDate - date < t);
    },

    // User functions

    // Trigger Events manually
    triggerKeyBoardEvent: function(e) {
        var self = this;
        return self._event_keydown(e);
    },

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
        self._currentProgressSpan.text(_formatTime(0));

        $(".activeTranscript").each( function() { $(this).removeClass("activeTranscript"); } );
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
        var p = Math.max(Math.min(parseInt(pos) / 100, 1), 0);
        self.element[0].currentTime = duration * p;
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

/**
 * Main player widget
 *
 * The "player" widget defines a HTML5 video player. It instanciates a
 * video() object by specifying an independant container. The
 * container itself is derived from jqueryui.dialog, with some
 * additional features.
 */
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
        // Default behaviour: fixed position
        uiPlayer.css('position', 'fixed');

        /* Minimized icon */
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
                uiPlayer.show();
                // Set player on a visible part of the screen
                if (uiPlayer.css('position') == 'absolute' &&
                    (($(document).scrollTop() > uiPlayer.position().top + uiPlayer.height())||
                     ($(document).scrollTop() + $(window).height() < uiPlayer.position().top)))
                    uiPlayer.css( { position: 'absolute',
                                    top:  event.pageY - uiPlayer.height() - 20 } );
                self.minplayer.hide("transfer", options, 1000, function(){} );
                self.minplayer.hide();
                return false;
            });

        uiPlayer
            .bind('dragstop', function(event, ui) {

            })
            .bind('resizestart', function(event, ui) {

            })
            .bind('resizestop', function(event, ui) {
                vid = uiPlayer.find('video', this);
                content=uiPlayer.find('.ui-dialog-content ', this);
                control=uiPlayer.find('.ui-video-control ', this);

                $(content).position({
                    my: "left top",
                    at:"left bottom",
                    of: uiPlayer.find('.ui-dialog-titlebar'),
                    offset: "1",
                    collision: "none"
                });
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
                if (uiPlayer.find('.ui-dialog-titlebar-fixonscreen', this).is(':hidden')) {
                    var pos = uiPlayer.position();
                    uiPlayer.css('position', 'fixed');
                    uiPlayer.css('top', pos.top - $(window).scrollTop());
                }
            });

        videoObject = uiPlayer.find('video', this);
        videoObject.video();
        videoObject.video('option', 'endFragmentBehaviour', 'continue');

        uiPlayer.find('.ui-dialog-titlebar-close ', this).remove();

        uiPlayerTitlebar=uiPlayer.find('.ui-dialog-titlebar ', this);

        // Fragment title
        uiPlayerFragmentTitle = $('<strong/>')
            .text("Fragment play")
            .addClass("ui-dialog-fragment-title")
            .hide()
            .appendTo(uiPlayer);

        //  Minimisation icon
        uiPlayerTitlebarToggle = $('<a href="#"/>')
            .addClass('ui-dialog-titlebar-toggle ' + 'ui-corner-all')
            .attr('role', 'button')
            .hover(
                function() { $(this).addClass('ui-state-hover'); },
                function() { $(this).removeClass('ui-state-hover'); }
            )
            .focus(function() { $(this).addClass('ui-state-focus'); })
            .blur(function() { $(this).removeClass('ui-state-focus'); })
            .mousedown(function(ev) { ev.stopPropagation(); })
            .click(function(event) {
                uiPlayer.hide();
                self.minplayer.show();
                return false;
            })
            .appendTo(uiPlayerTitlebar);

        uiPlayerTitlebarToggleText = (this.uiPlayerTitlebarToggleText = $('<span/>'))
            .addClass('ui-icon ' +'ui-icon-minusthick')
            .text('Toggle Player')
            .attr('title','Minimize Player')
            .appendTo(uiPlayerTitlebarToggle);

        // Thumbtack the player on the window (it will scroll with the content)
        uiPlayerTitlebarFixonScreen = $('<a href="#"/>')
            .addClass('ui-dialog-titlebar-fixonscreen ' +'ui-corner-all')
            .attr('role', 'button')
            .hover(function() {$(this).addClass('ui-state-hover');},
                   function() {$(this).removeClass('ui-state-hover');}
                  )
            .focus(function() {$(this).addClass('ui-state-focus');})
            .blur(function() {$(this).removeClass('ui-state-focus');    })
            .mousedown(function(ev) {
                ev.stopPropagation();
            })
            .click(function(event) {
                $(this).hide();
                var pos = uiPlayer.position();
                uiPlayer.css('position', 'fixed');
                uiPlayer.css('top',pos.top - $(window).scrollTop());
                uiPlayer.find('.ui-dialog-titlebar-nofixonscreen ',this).show();
                return false;
            })
            .appendTo(uiPlayerTitlebar)
            .hide();

        uiPlayerTitlebarFixonScreenText = (this.uiPlayerTitlebarFixonScreenText = $('<span/>'))
            .addClass('ui-icon ' +'ui-icon-pin-s')
            .text("Fix On Screen")
            .attr('title','Fix Player On Screen (fixed)')
            .appendTo(uiPlayerTitlebarFixonScreen);

        // Do not thumbtack the player on the window (it will not scroll with the content)
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
                var pos = uiPlayer.position();
                uiPlayer.css('position','absolute');
                uiPlayer.css('top', pos.top);
                uiPlayer.find('.ui-dialog-titlebar-fixonscreen ').show();
                return false;
            })
            .appendTo(uiPlayerTitlebar)
            .show();

        uiPlayerTitlebarNoFixonScreenText = (this.uiPlayerTitlebarNoFixonScreenText = $('<span/>'))
            .addClass('ui-icon ' +'ui-icon-pin-w')
            .text('options')
            .attr('title','Fix Player on its Page (absolute)')
            .appendTo(uiPlayerTitlebarNoFixonScreen);

        // Control function
        self.fragmentPlay = function(debut, fin, title, endFragBehav) {
            videoObject.video('fragmentPlay', debut, fin, self.options.endFragmentBehaviour);
            uiPlayer.find(".ui-dialog-fragment-title").show();
            if (!title)
                switch (self.options.endFragmentBehaviour) {
                case "continue":
                    title = "Playing from " + _formatTime(debut);
                    break;
                case "pause":
                case "stop":
                    title = "Playing from " + _formatTime(debut) + " to " + _formatTime(fin);
                    break;
                default:
                    // Loop
                    title = "Looping from " + _formatTime(debut) + " to " + _formatTime(fin);
                    break;
                }
            uiPlayer.find(".ui-dialog-fragment-title").text(title);
            self.minplayer.click();
        };
    };

    // Capture CTRL + KEY events and forward them to the video widget of the main player
    document.onkeydown = function(e) {
        if (e.ctrlKey == 1 && uiPlayer != undefined) {
            uiPlayer.find('video', this).video('triggerKeyBoardEvent', e);
        }
    };

    $.ui.player.prototype.videoObject = null;
    $.ui.player.prototype.options.title = 'Advene player';
    $.ui.player.prototype.options.endFragmentBehaviour = "continue";
    $.ui.player.prototype.options.position = "right";
    $.ui.player.prototype.options.resizable = "se";


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
            // Check for video type support
            videotype="none";
            v = document.createElement("video");
            if (v.canPlayType)
            {
                if (v.canPlayType("video/mp4"))
                {
                    videotype = "mp4";
                } else if (v.canPlayType("video/ogg"))
                {
                    videotype = "ogv";
                }
            }

            $("[target='video_player']").each( function() {
                var data = /(.+)#t=([.\d]+)?,([.\d]+)?/.exec($(this).attr('href'));
                if (data) {
                    var v = data[1];
                    if (v.match(/(.+)\.mp4/) && videotype == "ogv")
                    {
                        // mp4 file on a browser that only supports
                        // ogg. Try to fallback to .ogv.
                        v = v.match(/(.+)\.mp4/)[1] + ".ogv";
                    }
                    if (video_url == "")
                        video_url = v;
                    $(this).attr( { 'data-video-url': v,
                                    'data-begin': data[2],
                                    'data-end': data[3]
                                  });
                    if (!$(this).attr("title"))
                        $(this).attr("title", _formatTime(data[2]) + " - " + _formatTime(data[3]));
                    $(this).attr('href', '#');
                    $(this).click(function() {
                        return false;
                    });
                }
                $(this).advene('overlay');
            });

            if ($(".highlightRelated", document).length > 0) {
                $(".transcript[data-begin]").each( function() {
                    $(this).mouseover( function() {
                        /* Highlight related */
                        self = this;
                        begin = $(self).attr('data-begin');
                        end = $(self).attr('data-end');
                        $(".transcript[data-begin]", $(document)).each( function() {
                            if (Math.max(begin, $(this).attr('data-begin')) < Math.min(end, $(this).attr('data-end'))) {
                                $(this).addClass('relatedTranscript');
                            }
                        });
                    })
                        .mouseout( function() {
                            $(".relatedTranscript", $(document)).each( function() { $(this).removeClass('relatedTranscript'); });
                        });
                });
            }

            $("body").append("<div class='player_container' style='position:relative; overflow:visible; '>" +
                             "<video preload='none' style='overflow:visible; width:100%; height:auto; border:thick #00FF00; top:10; bottom:10;right:10;left:10; ' src='" + video_url + "'>" +
                             "</video></div>");

            playerOptions =  { title:'Advene main player',
                               endFragmentBehaviour: 'continue'
                             };
            if (options !== undefined)
                for (key in options)
                    playerOptions[key] = options[key];
            $('.player_container').player( playerOptions );

            check_hash = function () {
                // Check location.hash. If it is set, we look for the
                // first child containing a time reference and start
                // playing from this position.
                if (window.location.hash.length) {
                    hash = window.location.hash.substr(1);
                    nodes = $("[name="+hash+"]").find('[data-begin]:first');
                    if (! nodes.length) {
                        // Not found in children. Try in the siblings.
                        nodes = $("[name="+hash+"]").siblings().find('[data-begin]:first');
                    }
                    if (nodes.length) {
                    //console.log("Playing directly at " + nodes.attr('data-begin'));
                        $('.player_container').player('fragmentPlay',
                                                      nodes.attr('data-begin'),
                                                      nodes.attr('data-end'));
                    }
                }
            };
            // For initial document loading
            check_hash();
            // When following links inside the same document
            window.onhashchange = function () { check_hash(); };

            function filterHighlight(s)
            {
                if (s === "")
                {
                    this.previousFilterExpression = s;
                    $(".filteredText").each( function () {
                                                 $(this).replaceWith(this.innerHTML);
                                                 this.normalize();
                                             });
                    $("p.transcription").show();
                }
                else
                {
                    if (this.filterPreviousExpression === undefined || s.indexOf(this.filterPreviousExpression) != 0)
                    {
                        // Not the continuation of a previous expression. Reset hidden state
                        $("p.transcription").show();
                    }
                    this.filterPreviousExpression = s;

                    $(".filteredText").each( function () {
                                                          $(this).replaceWith(this.innerHTML);
                                                          this.normalize();
                                                      });
                    $("p.transcription").find("span").highlight(s, 'filteredText');
                    $("p.transcription").filter( function () { return $(this).find(".filteredText").length == 0 }).hide()
                }
            }

            // To activate filterBox, declare a <div id="filterBox"></div> in your document.
            if ($("#filterBox", document).length > 0)
            {
                $("#filterBox").append('<input id="filterInput" type="text" value="" /><button id="filterClear" value="Clear" />');
                $("#filterInput").keyup(function (event) { if (event.keyCode == 13) { filterHighlight($("#filterInput").attr("value")); } });
                $("#filterClear").click(function () { $("#filterInput").attr("value", ""); filterHighlight(""); });
            }

            uiPlayer.find("video")[0].load();
        },

        'overlay': function() {
            // overlay plugin.
            // The overlay function transforms MediaFragment-type links into calls to the video() object API.
            // On elements of class "screenshot", it overlays a menu that proposes to launch the player either embedded in the document, or as main player.
            var options = {
                border_color : '#666',
                overlay_color : '#000',
                overlay_text_color : '#666'
            };

            var self = this;

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
                .attr("class", 'screenshot-overlay-menu')
                .appendTo( $(self));

            var  $option = $('<img/>')
                .attr('src', './resources/HTML5/view_here.png')
                .appendTo($optionPlay)
                .click( function() {
                    node = $('.screenshot', self).parent();
                    $('.screenshot', self).hide();
                    $('.caption', self).hide();
                    $('.screenshot-overlay-menu', self).removeClass('screenshot-overlay-menu').addClass('screenshot-overlay-player');
                    $(this).parent().advene('player', node.attr('data-video-url'), node.attr('data-begin'), node.attr('data-end'));
                });

            option = $('<img/>')
                .attr('src', './resources/HTML5/view_player.png')
                .css('top', 30)
                .click( function(event){
                    node = $('.screenshot', self).parent();
                    $('.player_container').player('fragmentPlay', node.attr('data-begin'), node.attr('data-end'), fragmentTitle);

                    // Positioning player on screen when it's no longer visible (due to a scroll).
                    if ( ($(document).scrollTop() > $('.player_container').parent().position().top + $('.player_container').parent().height())
                         || ($(document).scrollTop() + $(window).height() < $('.player_container').parent().position().top) )
                        $('.player_container').parent().css( { position:'absolute', top: event.pageY - 50 } );
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
                $('.screenshot-overlay-menu', this).fadeIn(800);
            },
                          function() {
                              $('.caption', this).stop().animate( {
                                  top: imageHeight + 'px'
                              }, {
                                  queue: false
                              });
                              $('.screenshot-overlay-menu', this).fadeOut(200);
                          });

            self.bind( "fragmentclose", function(event, parentC) {
                $(parentC).find('.screenshot').show();
                $(parentC).find('.caption').show();
                $(parentC).find('.screenshot-overlay-player').removeClass('screenshot-overlay-player').addClass('screenshot-overlay-menu');
                self.die();
                       } );
            return true;
        },

        'player': function(videoURL, startx, endx) {
            // The player tool defines a screenshot-overlayed player
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
                                    'src': videoURL,
                                    'poster': 'resources/HTML5/advene_logo.png'
                                }
                               )
                    .css('position', 'absolute')
                    .prependTo(self._videoContainer);

                $(self._video).video({
                                 'overlay': 'true',
                                 'startPoint': self.options.start_point,
                                 'endPoint': self.options.end_point,
                                 'poster':'resources/HTML5/advene_logo.png',
                                 'autoPlay': false
                                 });

                parentC = $(self).parent();
                parentC.append(self._videoContainer);
                //destroy();
                self._videoContainer
                    .css('height','100%')
                    .css('width','100%');

                self.bind("destroySamplePlayer", destroySamplePlayer );
                $(self._video).hide();
                $(self._video).fadeIn('5000');
            });
            function destroySamplePlayer() {
                $(self._video).video("destroy");
                self._video.remove();
                self._videoContainer.empty();
                self._videoContainer.remove();
                self.removeClass('video-container');
                parentC.find('.screenshot:first').trigger('fragmentclose',parentC);
                self.unbind( "destroySamplePlayer", destroySamplePlayer );

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
            return undefined;
        }
  };

     $.fn.highlight = function (str, className) {
         var regex = new RegExp(str, "gi");
         return this.each(function () {
                              $(this).contents().filter(function() {
                                                            return this.nodeType == 3 && regex.test(this.nodeValue);
                                                        }).replaceWith(function() {
                                                                           return (this.nodeValue || "").replace(regex, function(match) {
                                                                                                                     return "<span class=\"" + className + "\">" + match + "</span>";
            });
        });
    });
};
})(jQuery);
