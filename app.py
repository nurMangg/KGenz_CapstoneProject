from flask import Flask, render_template, request, redirect, Response, url_for, session, flash
from flask_session import Session
import os
from PIL import Image
import base64
import io
import datetime
import json

#Password Hashing
from flask_bcrypt import Bcrypt

#Model
from model import preprocess_img, predict_result, facecrop
from model_chatbot import chatbot_response

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
    date = db.Column(db.DateTime, default=datetime.datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<History(id={self.id}, result={self.result})>'

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.datetime.now)
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
        user = User(
            fullname = request.form['fullName'],
            email = request.form['email'],
            password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8'),
        )
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
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
        
        if request.method == 'POST':
            word = request.form['review']
            predict = predict_sentiment(word)
            
            review = Review(
                review = word,
                score = int(predict),
                user_id = session['user_id']
                
            )
            
            db.session.add(review)
            db.session.commit()
            
            getReview = Review.query.order_by(Review.date.desc()).limit(5).all()
            
            
            return render_template("user/layanan.html", predict = predict, active = view, title = title, review = getReview)
            
        getReview = Review.query.order_by(Review.date.desc()).limit(5).all()
        return render_template("user/layanan.html", active = view, title = title,predict = predict, review = getReview)


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
        history = db.session.query(History.result, func.count(History.result)).where(History.user_id == session['user_id']).group_by(History.result).all()
        
        for history in history:
            if history[0] == 3:
                t0 = history[1]
            elif history[0] == 4:
                t1 = history[1]
            elif history[0] == 1 or history[0] == 5:
                t2 = history[1]
            elif history[0] == 2 or history[0] == 0:
                t3 = history[1]
            else:
                none = history
        
        hist = [t0, t1, t2, t3]    
        # print(session['user_id'])
        # print(history)
        print(hist)
        title = "K-Genz | History"
        return render_template("user/history.html", hist = hist, title = title)

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
                
                #save database history
                hist = History(
                    result = str(pred),
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
    
    hist = History(
        result = str(pred),
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
    
if __name__ == '__main__':
	app.run(debug=True)