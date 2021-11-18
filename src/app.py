#from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from db import *
from flask import Flask, request
import json
from datetime import datetime
from flask_apscheduler import APScheduler
import os

def success_response(data, code=200):
    return json.dumps(data), code

def failure_response(error, code=404):
    return json.dumps({'success': False, 'error': error}), code

if __name__ == '__main__':
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    sched = APScheduler()
    sched.init_app(app)
    sched.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)