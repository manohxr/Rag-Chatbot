from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

# Make sure the upload folder exists
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'Data')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def reverse_message(message):
    return message[::-1]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    reversed_message = reverse_message(user_message)
    return jsonify({'response': reversed_message})

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

if __name__ == '__main__':
    app.run(debug=True)
