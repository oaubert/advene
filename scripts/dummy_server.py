#!/usr/bin/python

import BaseHTTPServer
import json
import random
import urlparse

concepts = [ "dog", "cat", "bird", "tree", "human" ]

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
        json.dump({"status": 200, "message": "OK"}, s.wfile)

    def do_POST(s):
        length = int(s.headers['Content-Length'])
        body = s.rfile.read(length).decode('utf-8')
        if s.headers['Content-type'] == 'application/json':
            post_data = json.loads(body)
        else:
            post_data = urlparse.parse_qs(body)
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        json.dump({"status": 200, "message": "OK", "data": [
            {
                'confidence': random.random(),
                'timecode': random.randrange(post_data['begin'], post_data['end']),
                'label': random.choice(concepts),
                'uri': 'http://concept.org/%s' % random.choice(concepts)
            } for c in range(3)
        ]}, s.wfile)

if __name__ == '__main__':
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), RESTHandler)
    print "Starting dummy REST server on %s:%d" % (HOST_NAME, PORT_NUMBER)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
