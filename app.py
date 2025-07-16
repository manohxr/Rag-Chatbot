from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from src.helper import answer_query, update_index

app = Flask(__name__)
app.secret_key = 'rag_chatbot'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# Create user model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

# Create DB tables
with app.app_context():
    db.create_all()

UPLOAD_ROOT = os.path.join(os.getcwd(), 'Data')
os.makedirs(UPLOAD_ROOT, exist_ok=True)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)

        if User.query.filter_by(username=username).first():
            return "Username already exists!"
        
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        # Make user upload folder
        os.makedirs(os.path.join(UPLOAD_ROOT, username), exist_ok=True)

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({'response': 'Unauthorized'}), 401

    data = request.get_json()
    user_message = data.get('message', '')
    response_text = answer_query(user_message, session['username'])
    return jsonify({'response': response_text})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'username' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    username = session['username']
    if 'pdf' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'message': 'Only PDF files allowed'}), 400

    user_folder = os.path.join(UPLOAD_ROOT, username)
    os.makedirs(user_folder, exist_ok=True)

    save_path = os.path.join(user_folder, file.filename)
    file.save(save_path)

    update_message = update_index(username)
    return jsonify({'message': f'File {file.filename} uploaded! {update_message}'}), 200

if __name__ == '__main__':
    app.run(debug=True)
