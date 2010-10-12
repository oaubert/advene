/**
 * SVG specific functions
 *
 * This really should be integrated in the advene.js jQuery file, but
 * jQuery/SVG have some issues. Let's use a custom file for the moment.
 **/
var svgns = 'http://www.w3.org/2000/svg';
var time_marker = undefined;
var player = undefined;
var scale_layout;
var annotations_layout;
var svg;

// HTML5 Video player
function playerClick(a) {
    player.src = a.getAttribute('data-video-url');
    player.load();
    setTimeout(function() {
        player.currentTime = a.getAttribute('data-begin');
        player.play();
    }, 500);
    return false;
}

function hook_video_player() {
    var anchors = document.getElementsByTagName("a");
    for (var i = 0 ; i < anchors.length ; i++) {
        anchor = anchors[i];
        if (anchor.getAttribute("target") == "video_player") {
            // Parse href
            data = /(.+)#t=([.\d]+)?,([.\d]+)?/.exec(anchor.getAttribute("xlink:href"));
            if (data) {
                anchor.setAttribute('data-video-url', data[1]);
                anchor.setAttribute('data-begin', data[2]);
                anchor.setAttribute('data-end', data[3]);
                anchor.setAttribute("xlink:href", "#");
                anchor.setAttribute('onclick', 'playerClick(this); return false');
                }
            }
    }
}

function update_position(evt) {
    t = player.currentTime * 1000;
    if (t > 0 && time_marker) {
        time_marker.setAttribute("x1", t);
        time_marker.setAttribute("x2", t);
    }
}

function advene_svg_init(event) {
    hook_video_player();

    player = document.getElementById("video_player");
    scale_layout = document.getElementById("scale_layout");
    annotations_layout = document.getElementById("annotations_layout");
    svg = document.getElementsByTagName("svg")[0];

    // Define time marker
    time_marker = annotations_layout.ownerDocument.createElementNS(svgns, "line");
    time_marker.setAttributeNS(svgns, "id", "time_marker");
    time_marker.setAttribute("x1", 0);
    time_marker.setAttribute("y1", 0);
    time_marker.setAttribute("x2", 0);
    time_marker.setAttribute("y2", annotations_layout.getBBox().height);
    time_marker.setAttribute("opacity", .7);
    time_marker.setAttribute("stroke-width", "2px");
    time_marker.setAttribute("fill", "red");
    time_marker.setAttribute("stroke", "red");
    annotations_layout.appendChild(time_marker);

    // Position video player just below annotations
    player.style.top = svg.height.baseVal.value + 30;
    player.addEventListener("timeupdate", update_position, true);
    console.log("Advene HTML5 init");
}

function onLoadHandler(init_fxn){
    var old_init = window.onload;
    var new_init = init_fxn;
    window.onload = function() {
         if (typeof(old_init) == "function") {
             old_init();
         }
        new_init();
    }
    return this;
}

onLoadHandler(advene_svg_init);
