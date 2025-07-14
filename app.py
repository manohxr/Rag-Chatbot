from flask import Flask, render_template, request, jsonify
import os
from src.helper import answer_query, update_index

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'Data')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    response_text = answer_query(user_message)
    return jsonify({'response': response_text})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400

    file = request.files['pdf']

    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'message': 'Only PDF files are allowed'}), 400

    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(save_path)

    # Immediately update index with new PDF
    update_message = update_index()

    return jsonify({'message': f'File {file.filename} uploaded! {update_message}'}), 200

if __name__ == '__main__':
    app.run(debug=True)
