from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from src.helper import answer_query_stream, update_index, create_or_get_index
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rag_chatbot'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('chat_history', lazy=True))

class UserPDF(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pdf_name = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('pdfs', lazy=True))

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
    namespace = data.get('namespace')

    def generate():
        bot_chunks = []
        for chunk in answer_query_stream(user_message, session['username'], namespace):
            bot_chunks.append(chunk)
            yield chunk

        full_bot_response = ''.join(bot_chunks)
        user = User.query.filter_by(username=session['username']).first()
        new_chat = ChatHistory(
            user_id=user.id,
            user_message=user_message,
            bot_response=full_bot_response
        )
        db.session.add(new_chat)
        db.session.commit()

    return Response(stream_with_context(generate()), mimetype='text/plain')

@app.route('/get_history', methods=['GET'])
def get_history():
    if 'username' not in session:
        return jsonify([])

    user = User.query.filter_by(username=session['username']).first()
    chats = ChatHistory.query.filter_by(user_id=user.id).order_by(ChatHistory.timestamp).all()

    history = []
    for chat in chats:
        history.append({
            'user_message': chat.user_message,
            'bot_response': chat.bot_response,
            'timestamp': chat.timestamp.isoformat()
        })

    return jsonify(history)

@app.route('/get_pdfs', methods=['GET'])
def get_pdfs():
    if 'username' not in session:
        return jsonify([])

    user = User.query.filter_by(username=session['username']).first()
    pdfs = UserPDF.query.filter_by(user_id=user.id).all()

    pdf_list = []
    for pdf in pdfs:
        pdf_list.append({
            'id': pdf.id,
            'pdf_name': pdf.pdf_name,
            'uploaded_at': pdf.uploaded_at.isoformat()
        })

    return jsonify(pdf_list)

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'username' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    username = session['username']
    user = User.query.filter_by(username=username).first()

    if 'pdf' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'message': 'Only PDF files allowed'}), 400

    # Save file
    user_folder = os.path.join(UPLOAD_ROOT, username)
    os.makedirs(user_folder, exist_ok=True)
    save_path = os.path.join(user_folder, file.filename)
    file.save(save_path)

    namespace = os.path.splitext(file.filename)[0]

    # Call your indexing logic
    update_message, chunks_indexed = update_index(username, namespace)

    if not chunks_indexed:
        # Clean up: delete the file to keep it clean
        os.remove(save_path)
        return jsonify({
            'message': f'File {file.filename} uploaded but contains no valid text — nothing was indexed.'
        }), 400

    # Only add DB entry if chunks actually indexed
    existing = UserPDF.query.filter_by(user_id=user.id, pdf_name=namespace).first()
    if not existing:
        new_pdf = UserPDF(user_id=user.id, pdf_name=namespace)
        db.session.add(new_pdf)
        db.session.commit()

    return jsonify({
        'message': f'File {file.filename} uploaded and indexed!',
        'namespace': namespace
    }), 200


@app.route('/delete_pdf', methods=['POST'])
def delete_pdf():
    if 'username' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    pdf_name = data.get('pdf_name')

    username = session['username']
    index = create_or_get_index(username)
    index.delete(namespace=pdf_name, delete_all=True)  

    # Delete DB entry
    user = User.query.filter_by(username=username).first()
    pdf_entry = UserPDF.query.filter_by(user_id=user.id, pdf_name=pdf_name).first()
    if pdf_entry:
        db.session.delete(pdf_entry)
        db.session.commit()

    # Delete file
    pdf_path = os.path.join(UPLOAD_ROOT, username, f"{pdf_name}.pdf")
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    return jsonify({'message': f"PDF '{pdf_name}' deleted!"})

if __name__ == '__main__':
    app.run(debug=True)
