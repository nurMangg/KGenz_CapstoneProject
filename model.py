# Importing required libs
from tensorflow.keras.models import load_model
from keras_metrics import f1_score
from keras.preprocessing import image
from keras.utils import img_to_array
import numpy as np
import os
from PIL import Image
from skimage.transform import resize
from flask import Flask

import cv2

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Loading model

def facecrop(image):
    facedata = os.path.join(os.path.dirname(__file__), 'static/haarcascades/haarcascade_frontalface_default.xml')
    cascade = cv2.CascadeClassifier(facedata)

    img = cv2.imread(image)

    minisize = (img.shape[1],img.shape[0])
    miniframe = cv2.resize(img, minisize)

    faces = cascade.detectMultiScale(miniframe)

    for f in faces:
        x, y, w, h = [ v for v in f ]
        cv2.rectangle(img, (x,y), (x+w,y+h), (255,255,255))

        sub_face = img[y:y+h, x:x+w]
        fname, ext = os.path.splitext(image)
        final = cv2.cvtColor(sub_face, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(fname+ext, final)

    return


# Preparing and pre-processing the image
def preprocess_img(img_path):
    img = image.load_img(img_path, target_size=(48, 48, 3))
    # img = op_img.resize((48, 48))
    # img = np.array(img)
    img = np.expand_dims(img, axis=0)
    
    
    return img
 
 
# Predicting function
def predict_result(predict):
    model = load_model(os.path.join(os.path.dirname(__file__), 'models/citradigital/model.h5'), custom_objects={'f1_score': f1_score})
    pred = model.predict(predict)
    predicted = np.argmax(pred[0])
    # classes=['fear', 'angry', 'disgust', 'happy', 'neutral', 'sad']
    
    #print(predicted)
    print(pred)
    return predicted
    # if classes[predicted] == 'fear':
    #     return 0
    # elif classes[predicted] == 'angry':
    #     return 1
    # elif classes[predicted] == 'disgust':
    #     return 2
    # elif classes[predicted] == 'happy':
    #     return 3
    # elif classes[predicted] == 'neutral':
    #     return 4
    # else:
    #     return 5
    
