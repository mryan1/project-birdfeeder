# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


#!/usr/bin/python3

"""
Coral Smart Bird Feeder

Uses ClassificationEngine from the EdgeTPU API to analyze animals in
camera frames. Sounds a deterrent if a squirrel is detected.

Users define model, labels file, storage path, deterrent sound, and
optionally can set this to training mode for collecting images for a custom
model.

"""

import argparse
import time
import re
import imp
import logging
import gstreamer
from pycoral.utils import edgetpu
from pycoral.utils import dataset
from pycoral.adapters import common
from pycoral.adapters import classify
from pycoral.utils.edgetpu import make_interpreter
from PIL import Image
import piexif
from pushover import Client
import io


def send_alert(client, image, results):
  print('Sending alert... \n')
  b = io.BytesIO()
  #image.thumbnail(128,128)
  image.save(b, "JPEG")
  client.send_message(results, title="Bird Detected", attachment=b, sound="intermission")

def save_data(image,results,path,ext='jpg'):
    """Saves camera frame and model inference results
    to user-defined storage directory."""
    tag = '%010d' % int(time.monotonic()*1000)
    name = '%s/img-%s.%s' %(path,tag,ext)
    #add in exif data
    exif_dict = {'0th':dict}
    exif_dict['0th'] = {piexif.ImageIFD.ImageDescription : results[0][0]}
    image.save(name, "jpeg", exif=piexif.dump(exif_dict))
    print('Frame saved as: %s' %name)
    logging.info('Image: %s Results: %s', tag,results)

def load_labels(path):
    """Parses provided label file for use in model inference."""
    p = re.compile(r'\s*(\d+)(.+)')
    with open(path, 'r', encoding='utf-8') as f:
      lines = (p.match(line).groups() for line in f.readlines())
      return {int(num): text.strip() for num, text in lines}

def print_results(start_time, last_time, end_time, results):
    """Print results to terminal for debugging."""
    inference_rate = ((end_time - start_time) * 1000)
    fps = (1.0/(end_time - last_time))
    logging.info('Results: %s' ,results)
    print('\nInference: %.2f ms, FPS: %.2f fps' % (inference_rate, fps))
    for label, score in results:
      print(' %s, score=%.2f' %(label, score))

def do_training(results,last_results,top_k):
    """Compares current model results to previous results and returns
    true if at least one label difference is detected. Used to collect
    images for training a custom model."""
    new_labels = [label[0] for label in results]
    old_labels = [label[0] for label in last_results]
    shared_labels  = set(new_labels).intersection(old_labels)
    if len(shared_labels) < top_k:
      print('Difference detected')
      return True

def user_selections():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True,
                        help='.tflite model path')
    parser.add_argument('--labels', required=True,
                        help='label file path')
    parser.add_argument('--top_k', type=int, default=3,
                        help='number of classes with highest score to display')
    parser.add_argument('--threshold', type=float, default=0.1,
                        help='class score threshold')
    parser.add_argument('--storage', required=True,
                        help='File path to store images and results')
    parser.add_argument('--print', default=False, required=False,
                        help='Print inference results to terminal')
    parser.add_argument('--training', default=False, required=False,
                        help='Training mode for image collection')
    parser.add_argument('--rtspURL', required=False,
                        help='rtsp URL for external camera source')
    parser.add_argument('--pushoveruserkey', required=False,
                        help='Pushover user key for notifications')
    parser.add_argument('--pushoverapitoken', required=False,
                        help='Pushover api token for notifications')
    args = parser.parse_args()
    return args


def main():
    """Creates camera pipeline, and pushes pipeline through ClassificationEngine
    model. Logs results to user-defined storage. Runs either in training mode to
    gather images for custom model creation or in deterrent mode that sounds an
    'alarm' if a defined label is detected."""
    args = user_selections()
    print("Loading %s with %s labels."%(args.model, args.labels))
    engine = edgetpu.make_interpreter(args.model)
    engine.allocate_tensors()
    labels = load_labels(args.labels)

    storage_dir = args.storage
    rtspURL = args.rtspURL

    #Initialize logging file
    logging.basicConfig(filename='%s/results.log'%storage_dir,
                        format='%(asctime)s-%(message)s',
                        level=logging.DEBUG)

    #Initalize Pushover
    if args.pushoverapitoken is not None and args.pushoveruserkey is not None:
      logging.info("Initalizing pushover")
      client = Client(args.pushoveruserkey, api_token=args.pushoverapitoken)

    last_time = time.monotonic()
    last_saveimg = time.monotonic()
    last_alert = time.monotonic()
    last_results = [('label', 0)]
    def user_callback(image,fullimg):
        nonlocal last_time
        nonlocal last_results
        nonlocal last_saveimg
        nonlocal last_alert
        start_time = time.monotonic()
        interpreter = make_interpreter(*args.model.split('@'))
        interpreter.allocate_tensors()
        size = common.input_size(interpreter)
        image = image.resize(size, Image.ANTIALIAS)
        common.set_input(interpreter, image)

        interpreter.invoke()
        results = classify.get_classes(interpreter, top_k=1)

        end_time = time.monotonic()
        results = [(labels[i], score) for i, score in results]
        #print results 
        if args.print and results[0][0] !='patio, terrace' and results[0][0] !='picket fence, paling' and  results[0][1] > 0.65:
          print_results(start_time,last_time, end_time, results)
        #save img every 2 seconds as not to cause contraints waiting for writes to disk.  'lumbermill, sawmill'
        if results[0][0] !='patio, terrace' and results[0][0] !='picket fence, paling' and  results[0][0] !='bannister, banister, balustrade, balusters, handrail' and  results[0][0] !='lumbermill, sawmill' and results[0][1] > 0.70:
          if (time.monotonic() - last_saveimg) > 2:
            save_data(fullimg,results, storage_dir)
            last_saveimg = time.monotonic()
          if (time.monotonic() - last_alert) > 900 and args.pushoverapitoken and args.pushoveruserkey:
            send_alert(client, image, results[0][0])
            last_alert = time.monotonic()

        last_results=results
        last_time = end_time
    if rtspURL:
      result = gstreamer.run_pipeline(user_callback, rtspURL)

    else:
      result = gstreamer.run_pipeline(user_callback)

if __name__ == '__main__':
    main()
