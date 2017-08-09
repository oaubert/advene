#!/usr/bin/python

import logging
logger = logging.getLogger(__name__)

import BaseHTTPServer
import itertools
import json
import random
import urlparse

CONCEPT_LIST = [ "dog", "cat", "bird", "tree", "human" ]

HOST_NAME = 'localhost'
PORT_NUMBER = 9000

class RESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()

    def do_GET(s):
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        json.dump({"status": 200, "message": "OK", "data": {
            "capabilities": {
                "minimum_batch_size": 1, # # of frames
                "maximum_batch_size": 500, # # of frames
                "available_models": [ {
                    "id": "standard", # id of the model
                    "label": "Standard detection", # user-readable label for the model
                    "image_size": 224 # width/height for squared images
                }, {
                    "id": "dummy", # id of the model
                    "label": "Dummy detection", # user-readable label for the model
                    "image_size": 512 # width/height for squared images
                }
                ]
            }
        }}, s.wfile)

    def do_POST(s):
        length = int(s.headers['Content-Length'])
        body = s.rfile.read(length).decode('utf-8')
        if s.headers['Content-type'] == 'application/json':
            post_data = json.loads(body)
        else:
            post_data = urlparse.parse_qs(body)
        logger.info("Got a POST request [%d annotations, %d bytes]", len(post_data['annotations']), length)
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()

        for a in post_data['annotations']:
            logger.debug("Extracting for %s", a['annotationid'])
            # Emulate data extraction. 3 concepts max per annotation.
            concepts = []
            for _ in range(3):
                # The pseudo-detection takes place here :-)
                label = random.choice(CONCEPT_LIST)

                concepts.append({
                    'annotationid': a['annotationid'],
                    'confidence': random.random(),
                    # The following formula is here to make sure that
                    # we have a valid range even if the annotation
                    # bounds are invalid (begin == end or begin >
                    # end). In real code, it should be derived from
                    # the first annotation thumbnail were the concept
                    # is detected.
                    'timecode': random.randrange(a['begin'], a['begin'] + (max(a['end'] - a['begin'], 0) or 5000)),
                    'label': label,
                    'uri': 'http://concept.org/%s' % label
                    })
            a['concepts'] = concepts

        json.dump({
            "status": 200,
            "message": "OK",
            "data": {
                'media_filename': post_data.get('media_filename', ''),
                'media_uri': post_data.get('media_uri', ''),
                'model': post_data.get('model', ''),
                'concepts': list(itertools.chain(c for a in post_data['annotations'] for c in a['concepts']))
            }
        }, s.wfile)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), RESTHandler)
    logger.info("Starting dummy REST server on %s:%d", HOST_NAME, PORT_NUMBER)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
