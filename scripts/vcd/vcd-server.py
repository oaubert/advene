#!/usr/bin/python

import BaseHTTPServer
import json
import random
import urlparse

from keras.applications.resnet50 import ResNet50
from keras.preprocessing import image
from keras.applications.resnet50 import preprocess_input, decode_predictions
import numpy as np
from PIL import Image
from io import BytesIO
import base64
import itertools

HOST_NAME = ''
PORT_NUMBER = 9000

model = ResNet50(weights='imagenet')
target_size=(224,224)
top_n_preds = 3

class RESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        print "HEAD"
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()

    def do_GET(s):
        print "GET"
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        json.dump({"status": 200, "message": "OK"}, s.wfile)

    def do_POST(s):
        print "POST"
        length = int(s.headers['Content-Length'])
        body = s.rfile.read(length).decode('utf-8')
        if s.headers['Content-type'] == 'application/json':
            post_data = json.loads(body)
        else:
            post_data = urlparse.parse_qs(body)
        
        target_size 
        batch_x = np.zeros((len(post_data['frames']),target_size[0],target_size[1],3), dtype=np.float32) 
        for i,frame in enumerate(post_data['frames']):
            # Load image to PIL format
            img = Image.open(BytesIO(base64.b64decode(frame['screenshot'])))
            # cache frame - FIXME: currently there is no mean to identify the video - same timstamp will overwrite an old frame (hash?)
            img.save('/var/vcd/cache/{0}.png'.format(frame['timecode']))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # ResNet50 expects images at 224x224 scale:
            hw_tuple = (target_size[1], target_size[0])
            if img.size != hw_tuple:
                img = img.resize(hw_tuple)
            x = image.img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)
            batch_x[i] = x[0,:,:,:]
        preds = model.predict_on_batch(np.asarray(batch_x))
        
        # decode the results into a list of tuples (class, description, probability)
        # (one such list for each sample in the batch)
        decoded = decode_predictions(preds, top=top_n_preds)
        confidences = dict()
        for t in itertools.chain.from_iterable(decoded):
            if t[1] in confidences:
                confidences[t[1]].append(float(t[2]))
            else:
                confidences[t[1]] = [float(t[2])]
        
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        json.dump({"status": 200, "message": "OK", "data": [
            {
                'confidence': max(confidences[l]),
                'timecode': random.randrange(post_data['begin'], post_data['end']),
                'label': l,
                'uri': 'http://concept.org/%s' % l
            } for l in confidences
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
