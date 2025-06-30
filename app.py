from flask import Flask, jsonify
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Basic configuration (will be expanded later)
# We will use PostgreSQL via Docker, so DATABASE_URL will point to our container
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

@app.route('/')
def home():
    return "統一發票兌獎網站後端服務已啟動！"

@app.route('/api/status')
def status():
    return jsonify({"status": "ok", "message": "服務運行中"})

if __name__ == '__main__':
    # When running locally without Docker, we can use app.run()
    # But when run inside Docker, we'll use a production-ready server like Gunicorn
    app.run(debug=True, host='0.0.0.0') # host='0.0.0.0' allows access from outside the container in a Dockerized environment