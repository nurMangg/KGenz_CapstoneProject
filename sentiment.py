import numpy as np
from flask import Flask, request, render_template
import joblib
import os
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import CountVectorizer

model = joblib.load(open(os.path.join(os.path.dirname(__file__), 'models/sentiment_analysis/svm_model.pkl'), 'rb'))
cv = pickle.load(open(os.path.join(os.path.dirname(__file__), 'models/sentiment_analysis/cv.pickle'), 'rb'))



def predict_sentiment(test):
    test = [str(test)]
    test_vector = cv.transform(test).toarray()
    pred = model.predict(test_vector)
    return pred[0]



