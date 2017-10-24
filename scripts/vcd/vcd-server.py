#!/usr/bin/python3

import logging
logger = logging.getLogger(__name__)

import http.server
import json
import urllib.parse
import os

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

CACHE_DIR = "/var/vcd/cache"

models = [
    {
        "id": "standard",           #FIXME: improve selection of default model
        "label": "ResNet50",
        "image_size": 224
    },
    {
        "id": "resnet50",
        "label": "ResNet50",
        "image_size": 224
    },
]

model_impls = {
    "standard": {                   #FIXME: s.a.
        "class":ResNet50,
        "params": {'weights':'imagenet',},
    },
    "resnet50": {
        "class":ResNet50,
        "params": {'weights':'imagenet',},
    }
}

top_n_preds = 3

#create cachedir
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

class RESTHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()

    def do_GET(s):
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        response = json.dumps({"status": 200, "message": "OK", "data": {
            "capabilities": {
                "minimum_batch_size": 1, # # of frames
                "maximum_batch_size": 500, # # of frames
                "available_models": models
            }
        }})
        s.wfile.write(response.encode())

    def do_POST(s):
        length = int(s.headers['Content-Length'])
        body = s.rfile.read(length).decode('utf-8')
        if s.headers['Content-type'] == 'application/json':
            post_data = json.loads(body)
        else:
            post_data = urllib.parse.parse_qs(body)

        modelid = post_data['model']
        try:    
            model = model_impls[modelid]['class'](**model_impls[modelid]['params'])
        except Exception as e:
            logger.error("Unable to load model: {reason}".format(reason=e.message))
            s.send_response(300)
            s.send_header("Content-type", "application/json")
            s.end_headers()
            json.dump({
                    "status": 300,
                    "message": e.message,
                 }, s.wfile)
            return
        
        target_size = (dict([(m["id"],m['image_size']) for m in models]))[modelid]
        concepts = []
        for annotation in post_data['annotations']:
            aid = annotation['annotationid']
            begin = annotation['begin']
            begin = annotation['end']
            
            batch_x = np.zeros((len(annotation['frames']),target_size,target_size,3), dtype=np.float32)
            for i,frame in enumerate(annotation['frames']):
                # Load image to PIL format
                img = Image.open(BytesIO(base64.b64decode(frame['screenshot'])))
                # cache frame - FIXME: currently there is no mean to identify the video - same timstamp will overwrite an old frame (hash?)
                img.save(os.path.join(CACHE_DIR,'{0}.png'.format(frame['timecode'])))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                hw_tuple = (target_size, target_size)
                if img.size != hw_tuple:
                    logger.warn("Scaling image to model size - this should be done in advene!")
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
            logger.debug(confidences)
            
            concepts.extend([
            {
                'annotationid': aid,
                'confidence': max(confidences[l]),
                #FIXME: set correct timecode - set timecode of frame with max confidence?
                'timecode': annotation['begin'], #timestamp_in_ms,
                'label': l,
                'uri': 'http://concept.org/%s' % l
            } for l in confidences]
            )

        logger.debug(concepts)
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        response=json.dumps({
            "status": 200,
            "message": "OK",
            "data": {
                'media_filename': post_data["media_filename"],
                'media_uri': post_data["media_uri"],
                'concepts': concepts
            }
        })
        s.wfile.write(response.encode())

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server_class = http.server.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), RESTHandler)
    logger.info("Starting dummy REST server on %s:%d", HOST_NAME, PORT_NUMBER)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
