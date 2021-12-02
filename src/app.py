import json
import os
import datetime
from db import User, Plant, Asset, db
from config import Config
from constants import SECONDS_TO_MILLISECONDS_CONVERSION
from flask import Flask, request
from flask_apscheduler import APScheduler
from flask.globals import session


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
with app.app_context():
    db.create_all()

sched = APScheduler()
sched.init_app(app)
sched.start()


@sched.task('interval', id='update_time_elapsed', minutes=30)
def update_time_elapsed():
    with app.app_context():
        for plant in db.session.query(Plant).all():
            plant.time_elapsed = float(SECONDS_TO_MILLISECONDS_CONVERSION *
                                       (datetime.datetime.utcnow() - plant.start_time).total_seconds())
        db.session.commit()


def success_response(data, code=200):
    return json.dumps(data), code


def failure_response(error, code=404):
    return json.dumps({'success': False, 'error': error}), code


def extract_token(request):
    token = request.headers.get("Authorization")
    if token is None:
        return False, "Missing authorization header"
    token = token.replace("Bearer", "").strip()
    return True, token


@app.route("/register/", methods=["POST"])
def register_accont():
    body = json.loads(request.data)
    username = body.get('username')
    password = body.get('password')

    if username is None or password is None:
        return failure_response("Missing required arguments", 400)

    created, user = User.create_user(username, password)

    if not created:
        return failure_response("This username is already being used", 403)

    return success_response({
        "session_token": user.session_token,
        "session_expiration": str(user.session_expiration),
        "refresh_token": user.refresh_token,
        "refresh_expiration": str(user.refresh_expiration)
    }, 201)


@app.route("/login/", methods=["POST"])
def login():
    body = json.loads(request.data)
    username = body.get('username')
    password = body.get('password')

    if username is None or password is None:
        return failure_response("Missing required arguments", 400)

    valid_creds, user = User.verify_credentials(username, password)

    if not valid_creds:
        return failure_response("Invalid username or password")

    return success_response({
        "session_token": user.session_token,
        "session_expiration": str(user.session_expiration),
        "refresh_token": user.refresh_token,
        "refresh_expiration": str(user.refresh_expiration)
    })


@app.route("/reauthenticate/", methods=["POST"])
def reauthenticate():
    success, refresh_token = extract_token(request)

    if not success:
        return failure_response(refresh_token)

    valid, user = User.reauthenticate_session(refresh_token)

    if valid is False:
        return failure_response("Invalid update token")

    if valid is None:
        return failure_response("Refresh token has expired, must log-in again", 401)

    return success_response({
        "session_token": user.session_token,
        "session_expiration": str(user.session_expiration),
        "refresh_token": user.refresh_token,
        "refresh_expiration": str(user.refresh_expiration)
    })

@app.route('/plants/')
def get_all_plants():
    success, session_token = extract_token(request)
    if not success:
        return failure_response(session_token)

    user = db.session.query(User).filter(
        User.session_token == session_token
    ).first()

    if user is None:
        return failure_response("No user found")

    if not user.verify_session_token(session_token):
        return failure_response("Session token has expired, must reauthenticate", 403)

    plants = [p.serialize() for p in db.session.query(
        Plant).join(User).filter(User.id == user.id).all()]

    return success_response({
        'plants': plants
    })


@app.route('/plants/<int:id>/')
def get_a_plant(id):
    success, session_token = extract_token(request)
    if not success:
        return failure_response(session_token)

    user = db.session.query(User).filter(
        User.session_token == session_token
    ).first()

    if user is None:
        return failure_response("No user found")

    if not user.verify_session_token(session_token):
        return failure_response("Session token has expired, must reauthenticate", 403)

    plant = db.session.query(Plant).join(User).filter(
        User.id == user.id, Plant.id == id).first()

    if plant is None:
        return failure_response('No plant exists by this id.')

    return success_response(plant.serialize())


@app.route('/plants/remove/<int:id>/')
def remove_a_plant(id):
    success, session_token = extract_token(request)
    if not success:
        return failure_response(session_token)

    user = db.session.query(User).filter(
        User.session_token == session_token
    ).first()

    if user is None:
        return failure_response("No user found")

    if not user.verify_session_token(session_token):
        return failure_response("Session token has expired, must reauthenticate", 403)

    plant = db.session.query(Plant).join(User).filter(
        User.id == user.id, Plant.id == id).first()

    if plant is None:
        return failure_response('No plant exists by this id.')

    asset = db.session.query(Asset).join(Plant).filter(
        Plant.id == plant.id
    ).first()
    asset.remove_from_aws()

    db.session.delete(plant)

    db.session.commit()

    return success_response({
        "sucess": True,
        "response": "Plant removed successfully!"
    })


@app.route('/plants/', methods=['POST'])
def create_a_plant():
    body = json.loads(request.data)
    success, session_token = extract_token(request)
    if not success:
        return failure_response(session_token)

    user = db.session.query(User).filter(
        User.session_token == session_token
    ).first()

    if user is None:
        return failure_response("No user found")

    if not user.verify_session_token(session_token):
        return failure_response("Session token has expired, must reauthenticate", 403)

    watering_time = body.get('watering_time')
    name = body.get('name')
    image = body.get('image')
    if watering_time is None or name is None or image is None:
        return failure_response('The request is missing required information.', 400)

    plant = Plant(user_id=user.id, watering_time=watering_time,
                  name=name)

    db.session.add(plant)
    db.session.flush()

    asset = Asset(image=image, plant_id=plant.id)
    db.session.add(asset)

    asset.plant = plant
    plant.asset = asset
    plant.user = user
    user.plants.append(plant)

    db.session.commit()
    return success_response(plant.serialize(), code=201)

@app.route('/plants/water/<int:id>',  methods=['POST'])
def water_plant(id):
    success, session_token = extract_token(request)
    if not success:
        return failure_response(session_token)

    user = db.session.query(User).filter(
        User.session_token == session_token
    ).first()

    if user is None:
        return failure_response("No user found")

    if not user.verify_session_token(session_token):
        return failure_response("Session token has expired, must reauthenticate", 403)

    plant = db.session.query(Plant).join(User).filter(
        User.id == user.id, Plant.id == id).first()

    if plant is None:
        return failure_response('No plant exists by this id.')

    plant.start_time = datetime.datetime.now(datetime.datetime.timezone.utc)
    plant.time_elapsed = 0
    plant.watering_date = plant.start_time + datetime.datetime.timedelta(milliseconds=plant.watering_time)

    db.session.commit()
    return success_response(plant.serialize())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
