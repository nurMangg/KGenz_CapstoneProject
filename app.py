from flask import Flask, render_template, request, redirect, Response, url_for, session, flash, send_file
from flask_session import Session
import os
from PIL import Image
import base64
import io
from datetime import datetime
import json
from flask import jsonify

import pytz


#Password Hashing
from flask_bcrypt import Bcrypt

#Model
from model import preprocess_img, predict_result, facecrop
from model_chatbot import chatbot_response

from model_android import facecropAndroid,predict_resultForAndroid,preprocess_imgForAndroid
from model_chatbot_android import model,file_intents,file_words,file_classes,intents,words,classes,clean_up_sentence,bow,predict_class,getResponse,chatbot_response

#Sentiment Analysis
from sentiment import predict_sentiment

# Database
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String, and_, func


class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
db.init_app(app)
bcrypt = Bcrypt(app)

#session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(256), nullable=False)
    history = db.relationship("History", backref="user")
    review = db.relationship("Review", backref="user")
    
    def __repr__(self):
        return f'<User(id={self.id}, fullname={self.fullname})>'
    
class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    result = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<History(id={self.id}, result={self.result})>'

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<Review(id={self.id}, review={self.review})>'
    
with app.app_context():
    db.create_all()

@app.route("/list", methods=['GET', 'POST'])
def list():
    title = "K-Genz | List"
    users = db.session.execute(db.select(User).order_by(User.id)).scalars()
    historyq = db.session.execute(db.select(History).order_by(History.id)).scalars()
        
    return render_template("user/list.html", users = users, hist = historyq, title = title)
    
@app.route("/", methods=['GET', 'POST'])
def index():

    if request.method == 'POST':
        user = User.query.filter_by(email = request.form['email']).first()
        
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            flash('Login Success', 'success')
            session['user_id'] = user.id
            session['fullname'] = user.fullname
            return redirect(url_for('beranda'))
        else :
            flash('Please check your login details and try again.', 'danger')
            return render_template('user/index.html')
    
    if request.method == 'GET':
        title = "K-Genz | Login"
        return render_template("user/index.html", title = title)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        check = User.query.filter_by(email = request.form['email']).first()
        
        if check is not None:
            check_user = check.email.lower()
            if check_user == request.form['email'].lower() :
                flash('Email Telah digunakan', 'danger')
                return render_template('user/register.html')
        
        user = User(
            fullname = request.form['fullName'],
            email = request.form['email'],
            password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8'),
        )
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash('Akun Telah dibuat, silahkan melakukan login', 'success')
        return redirect(url_for('index'))
    
    
    title = "K-Genz | Register"
    return render_template("user/register.html", title = title)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/delete/<int:id>', methods=['POST', 'DELETE'])
def delete(id):
    user = db.session.execute(db.select(User).filter_by(id=id)).scalar_one()
    db.session.delete(user)
    db.session.commit()
    return 'success', 200

@app.route("/beranda")
def beranda():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        
        title = "K-Genz | Beranda"
        view = "beranda"
        return render_template("user/beranda.html", active = view, title = title, username = session['fullname'])
    
@app.route("/artikel")
def artikel(): 
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        title = "K-Genz | Artikel"
        view = "artikel"
        
        # get_artikel = getData_yt()
        get_artikel = json.load(open(os.path.join(os.path.dirname(__file__), "api/data_youtube.json")))
        
        return render_template("user/artikel.html", active = view, title = title, artikel = get_artikel["items"])
    
    
@app.route("/layanan", methods=['GET', 'POST'])
def layanan():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        title = "K-Genz | Layanan"
        view = "layanan"
        predict = 0
        
        sentiment = db.session.query(Review.score, func.count(Review.score)).group_by(Review.score).all()
        
        if request.method == 'POST':
            word = request.form['review']
            predict = predict_sentiment(word)
            
            utc_time = datetime.utcnow()

            target_timezone = 'Asia/Jakarta'
            local_timezone = pytz.timezone(target_timezone)
            local_time = pytz.utc.localize(utc_time).astimezone(local_timezone)
            
            review = Review(
                review = word,
                score = int(predict),
                date = local_time.replace(microsecond=0),
                user_id = session['user_id']
                
            )
            
            db.session.add(review)
            db.session.commit()
            
            getReview = Review.query.order_by(Review.date.desc()).limit(5).all()
            
            
            return render_template("user/layanan.html", predict = predict, active = view, title = title, review = getReview, sentiment=sentiment)
            
        getReview = Review.query.order_by(Review.date.desc()).limit(5).all()
        return render_template("user/layanan.html", active = view, title = title,predict = predict, review = getReview, sentiment=sentiment)


@app.route("/capture-layanan")
def camera():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        title = "K-Genz | Deteksi Stress"
        return render_template("user/viewCaptureCamera.html", title = title)



@app.route("/chatbot")
def chatbot():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        title = "K-Genz | Chatbot"    
        return render_template("user/chatbot.html", title = title)

@app.route("/chatbot_res")
def get_bot_response():
    userText = request.args.get('msg')
    return chatbot_response(userText)

@app.route("/history")
def history():
    t0 = 0
    t1 = 0
    t2 = 0
    t3 = 0
    
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        history = db.session.query(History.result).where(History.user_id == session['user_id']).all()
        
        for history in history:
            if history[0] == 3:
                t0 += 1
            elif history[0] == 4:
                t1 += 1
            elif history[0] == 1 or history[0] == 5:
                t2 += 1
            elif history[0] == 2 or history[0] == 0:
                t3 += 1
            else:
                none = history
        
        hist = [t0, t1, t2, t3]
        
        idq = session['user_id']
        history_user = db.session.execute(db.select(History).where(History.user_id == idq).order_by(History.id.desc())).scalars()
        
        title = "K-Genz | History"
        return render_template("user/history.html", hist = hist, title = title, ri = history_user)

@app.route("/profil", methods=['GET', 'POST'])
def profil():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        profil = User.query.get_or_404(session['user_id'])
        title = "K-Genz | Profil"
        view = "profil"
        
        if request.method == 'POST':
            profil.fullname = request.form['fullname']
            profil.email = request.form['email']
            db.session.commit()
            return redirect(url_for('profil'))
        
        return render_template("user/profil.html", active = view, title = title, user = profil)

@app.route("/profil_password", methods=['POST', 'GET'])    
def profil_password():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else:
        profil = User.query.get_or_404(session['user_id'])
        title = "K-Genz | Profil"
        view = "profil"
        
        if request.method == 'POST':
            pass_new = bcrypt.generate_password_hash(request.form['password_new']).decode('utf-8')
            if bcrypt.check_password_hash(profil.password, request.form['password']):
                if pass_new == profil.password:
                    flash('Password baru tidak boleh sama dengan password lama', 'danger')
                    return redirect(url_for('profil'))
                elif request.form['password_new'] != request.form['password_confirm']:
                    flash('Password baru tidak sesuai', 'danger')
                    return redirect(url_for('profil'))
                else:    
                    profil.password = pass_new
                    db.session.commit()
                    flash('Password berhasil diubah', 'success')
                    return redirect(url_for('profil'))
                
            else : 
                flash('Password lama tidak sesuai', 'danger')
                return redirect(url_for('profil'))
            
        return render_template("user/profil.html", active = view, title = title, user = profil)

@app.route('/uploadfile', methods=['POST'])
def upload_file():
    if session.get('user_id') is None:
        return redirect(url_for('index'))
    else :
        try:
            if request.method == 'POST':
                #usr
                user = User.query.get_or_404(session['user_id'])
                
                image = request.files['file']
                if image.filename != '':
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], image.filename))
                    sh_img = image.filename
                    
                facecrop(os.path.join(app.config['UPLOAD_FOLDER'], image.filename))
                img = preprocess_img(os.path.join(app.config['UPLOAD_FOLDER'], image.filename))
                pred = predict_result(img)
                
                utc_time = datetime.utcnow()

                target_timezone = 'Asia/Jakarta'
                local_timezone = pytz.timezone(target_timezone)
                local_time = pytz.utc.localize(utc_time).astimezone(local_timezone)
                
                #save database history
                hist = History(
                    result = str(pred),
                    date = local_time.replace(microsecond=0),
                    user_id = user.id
                )
                db.session.add(hist)
                db.session.commit()
                
                if pred == 4 :
                    preds = "Stress Tingkat Rendah"
                elif pred == 5 or pred == 1:
                    preds = "Stress Tingkat Sedang"
                elif pred == 2 or pred == 0:
                    preds = "Stress Tingkat Tinggi"
                else:
                    preds = "Tidak Ada Stress"

                datajson = json.load(open(os.path.join(os.path.dirname(__file__), "api/data_tingkatStress.json")))
                
                return render_template("user/resultCapture.html", sh_img=sh_img, predict=str(preds), data=datajson)
        except Exception as e:
            error = f"An error occurred: {str(e)}"
            return render_template("user/viewCaptureCamera.html", message=error)
    
    
@app.route('/save', methods=['POST'])
def save():
    data = request.get_json()
    if data and 'image' in data:
        img_data = data['image'].split(',')[1]
        image = Image.open(io.BytesIO(base64.b64decode(img_data)))
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], "capture-camera.png"))
        return 'success', 200
    return 'Error', 400

@app.route('/predict', methods=['GET','POST'])
def predict():
    facecrop(os.path.join(app.config['UPLOAD_FOLDER'], "capture-camera.png"))
    img = preprocess_img(os.path.join(app.config['UPLOAD_FOLDER'], "capture-camera.png"))
    pred = predict_result(img)
    
    utc_time = datetime.utcnow()

    target_timezone = 'Asia/Jakarta'
    local_timezone = pytz.timezone(target_timezone)
    local_time = pytz.utc.localize(utc_time).astimezone(local_timezone)
    
    hist = History(
        result = str(pred),
        date = local_time.replace(microsecond=0),
        user_id = session.get('user_id')
    )
    db.session.add(hist)
    db.session.commit()
    
    if pred == 4 :
        preds = "Stress Tingkat Rendah"
    elif pred == 5 or pred == 1:
        preds = "Stress Tingkat Sedang"
    elif pred == 2 or pred == 0:
        preds = "Stress Tingkat Tinggi"
    else:
        preds = "Tidak Ada Stress"
        
    datajson = json.load(open(os.path.join(os.path.dirname(__file__), "api/data_tingkatStress.json")))
        
    return render_template("user/resultCapture.html", sh_img="capture-camera.png", predict=str(preds), data = datajson)
 
 
# Android
#For Android Route 
@app.route("/chatbot_resAndroid", methods=['GET', 'POST'])
def get_bot_responseAndroid():
    if request.method == 'POST':
        data = request.get_json()
        user_text = data.get('msg')
        test = user_text
        result = chatbot_response(test) 
        
        response_data = {'response': result} 
        return jsonify(response_data)
    else:
        return jsonify({'error': 'Method not allowed'}), 405





@app.route("/loginAndroid", methods=['POST'])
def loginAndroid():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        user = User.query.filter(User.email == email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            return jsonify({
                'user_id': user.id,
                'fullname': user.fullname,  # Pastikan menggunakan fullname
                'email': user.email,
            }), 200
        else:
            return jsonify({'error': 'Invalid email or password'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    
@app.route('/uploadFileAndroid', methods=['POST'])
def uploadFileAndroid():
    if 'file' not in request.files:
        return 'No file part'

    file = request.files['file']

    if file.filename == '':
        return 'No selected file'


    file.save('android/images/' + file.filename)

    return 'File uploaded successfully'

@app.route('/registerAndroid', methods=['POST'])
def registerAndroid():
    try:
        data = request.get_json()
        new_user = User(
            fullname=data['fullname'],
            email=data['email'],
            # password=data['password']
            password = bcrypt.generate_password_hash(data['password']).decode('utf-8'),
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route("/profil_passwordAndroid", methods=['POST'])    
def profil_passwordAndroid():
        
        data = request.get_json()
        
        user_id = data.get('user_id')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        oldPassword = old_password
        newPassword = new_password
        confirmPassword = confirm_password
        
        
        profil = User.query.get_or_404(user_id)
   
        
        if request.method == 'POST':
            pass_new = bcrypt.generate_password_hash(newPassword).decode('utf-8')
            if bcrypt.check_password_hash(profil.password, oldPassword):
                if pass_new == profil.password:
                    # flash('Password baru tidak boleh sama dengan password lama', 'danger')
                    return jsonify({'message': 'Password baru tidak boleh sama dengan password lama'})
                elif newPassword != confirmPassword:
                    # flash('Password baru tidak sesuai', 'danger')
                    return jsonify({'message': 'Password baru tidak sesuai'})
                else:    
                    profil.password = pass_new
                    db.session.commit()
                    # flash('Password berhasil diubah', 'success')
                    return jsonify({'message': 'Password berhasil diubah'})
                
            else : 
                # flash('Password lama tidak sesuai', 'danger')
                return jsonify({'message': 'Password lama tidak sesuai'})
            
        return jsonify({'message': 'Sukses'})
     
    
@app.route("/profilAndroid", methods=['POST'])
def profil_android():
    data = request.get_json()

    user_id = data.get('user_id')
    new_fullname = data.get('fullname')
    new_email = data.get('email')
    
    userid = user_id
    userfullname = new_fullname
    useremail = new_email
    
    
    profil = User.query.get_or_404(user_id)
    if request.method == 'POST':
            profil.fullname = userfullname
            profil.email = useremail
            db.session.commit()
    
    

    # Lakukan sesuatu dengan data yang diterima, misalnya memperbarui database

    return jsonify({'message': "sukses"})
        


@app.route('/receive_json', methods=['POST'])
def receive_json():
    try:    
        utc_time = datetime.utcnow()

        target_timezone = 'Asia/Jakarta'
        local_timezone = pytz.timezone(target_timezone)
        local_time = pytz.utc.localize(utc_time).astimezone(local_timezone)
        
        data = request.get_json()
        received_text = data.get('text', '')
        userId = data.get('user_id')
        uploads = 'android/images/'
        
        fileName = received_text
        
        path = uploads + received_text
        # Lakukan sesuatu dengan data JSON yang diterima di server Flask
        print('JSON yang diterima:', data)
        
        facecropAndroid(path)
        img = preprocess_img(path)
        pred = predict_resultForAndroid(img)
        
        hist = History(
            result = str(pred),
            date = local_time.replace(microsecond=0),
            user_id = userId
        )
        db.session.add(hist)
        db.session.commit()

        if pred == 4 :
            preds = "Stress Tingkat Rendah"
        elif pred == 5 or pred == 1:
            preds = "Stress Tingkat Sedang"
        elif pred == 2 or pred == 0:
            preds = "Stress Tingkat Tinggi"
        else:
            preds = "Tidak Ada Stress"
        
        # Kirim respons JSON ke Flutter
        response_data = {'message': preds}
        
        return jsonify(response_data)
    except Exception as e:
        print(f'Error in receive_json: {e}')
        return jsonify({'message': 'Internal Server Error'}), 500

@app.route("/analisis_sentimen", methods=['GET', 'POST'])
def analisis_sentimen():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        received_text = data.get('text')  # Use 'text' as the key to match the Flutter app

        # Assuming predict_sentiment is a function that analyzes sentiment
        prediction = predict_sentiment(received_text)
        
        utc_time = datetime.utcnow()

        target_timezone = 'Asia/Jakarta'
        local_timezone = pytz.timezone(target_timezone)
        local_time = pytz.utc.localize(utc_time).astimezone(local_timezone)
        
        review = Review(
                review = received_text,
                date = local_time.replace(microsecond=0),
                score = int(prediction),
                user_id = user_id
                
            )
        db.session.add(review)
        db.session.commit()

        # Return the prediction as JSON response
        response_data = {'prediction': str(prediction)}
        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/download')
def download_file():
    file_path = os.path.join(os.path.dirname(__file__), "static/KGenz - Capstone Project.apk")
    return send_file(file_path, as_attachment=True)
   
if __name__ == '__main__':
	app.run(debug=True)