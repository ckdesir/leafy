import base64
import bcrypt
import boto3
import datetime
import hashlib
import os
import random
import re
import string
import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from io import BytesIO
from mimetypes import guess_extension, guess_type
from PIL import Image
from constants import EXTENSIONS, BASEDIR, S3_BUCKET, S3_BASE_URL

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)

    # User information
    username = db.Column(db.String, nullable=False, unique=True)
    password_digest = db.Column(db.String, nullable=False)
    plants = db.relationship(
        'Plant', back_populates='user', lazy=True, cascade='delete', uselist=True)

    # Session info
    session_token = db.Column(db.String, nullable=False, unique=True)
    session_expiration = db.Column(db.DateTime, nullable=False)
    refresh_token = db.Column(db.String, nullable=False, unique=True)
    refresh_expiration = db.Column(db.DateTime, nullable=False)

    def __init__(self, **kwargs):
        self.username = kwargs.get('username')
        self.password_digest = bcrypt.hashpw(kwargs.get(
            'password').encode('utf8'), bcrypt.gensalt(rounds=13))
        self.renew_session()

    # Used to randomly generate session/update token
    def _urlsafe_base_64(self):
        return hashlib.sha1(os.urandom(64)).hexdigest()

    # Generates new tokens, and resets expiration time
    def renew_session(self):
        self.session_token = self._urlsafe_base_64()
        self.session_expiration = datetime.datetime.now() + datetime.timedelta(days=1)
        self.refresh_expiration = datetime.datetime.now() + datetime.timedelta(days=60)
        self.refresh_token = self._urlsafe_base_64()

    def verify_password(self, password):
        return bcrypt.checkpw(password.encode('utf8'), self.password_digest)

    # Checks if session token is valid and hasn't expired
    def verify_session_token(self, session_token):
        return session_token == self.session_token and datetime.datetime.now() < self.session_expiration

    def verify_refresh_token(self, refresh_token):
        return refresh_token == self.refresh_token and datetime.datetime.now() < self.refresh_expiration

    @staticmethod
    def create_user(username, password):
        existing_user = db.session.query(User).filter(
            User.username == username).first()
        if existing_user is not None:
            return False, None

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return True, user

    @staticmethod
    def verify_credentials(username, password):
        existing_user = db.session.query(User).filter(
            User.username == username).first()
        if existing_user is None:
            return False, None

        verify_pass = existing_user.verify_password(password)
        if verify_pass is True:
            existing_user.renew_session()
            db.session.commit()

        return verify_pass, existing_user

    @staticmethod
    def reauthenticate_session(refresh_token):
        """
        Attempts to reauthenticate a session. If the user does not exist, returns
        false. If the refresh_token is expired, returns None. If a user does exist
        and is reauthenticated successfully, returns true and said user. 
        """
        existing_user = db.session.query(User).filter(
            User.refresh_token == refresh_token).first()

        if existing_user is None:
            return False, None

        # Check to make sure the refresh_token has not expired
        if existing_user.verify_refresh_token(refresh_token):
            existing_user.renew_session()
        else:
            return None, None

        db.session.commit()
        return True, existing_user


class Asset(db.Model):
    __tablename__ = 'asset'

    id = db.Column(db.Integer, primary_key=True)
    base_url = db.Column(db.String, nullable=True)
    salt = db.Column(db.String, nullable=False)
    extension = db.Column(db.String, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'),
                         nullable=False)
    plant = db.relationship(
        'Plant', back_populates='asset')

    def __init__(self, **kwargs):
        self._create(kwargs.get('image'))
        self.plant_id = kwargs.get('plant_id')

    def return_url(self):
        return f'{self.base_url}/{self.salt}.{self.extension}'

    def serialize(self):
        return {
            'url': f'{self.base_url}/{self.salt}.{self.extension}',
        }

    def _create(self, image_data):
        ext = guess_extension(
            guess_type(image_data[:image_data.find(',') + 1])[0])[1:]
        if ext not in EXTENSIONS:
            raise Exception(f'Extension {ext} is not supported! :(')

        # Creates a random name to represent the image in our bucket
        salt = ''.join(
            random.SystemRandom().choice(
                string.ascii_uppercase + string.digits
            )
            for _ in range(16)
        )

        # Extracts the image
        img_str = re.sub('^data:image/.+;base64,', '', image_data).strip()
        img_data = base64.b64decode(img_str)
        img = Image.open(BytesIO(img_data))

        # Initializes our Asset
        self.base_url = S3_BASE_URL
        self.salt = salt
        self.extension = ext
        self.width = img.width
        self.height = img.height
        self.created_at = datetime.datetime.now()

        img_filename = f'{salt}.{ext}'
        self._upload(img, img_filename)

    def _upload(self, img, img_filename):
        img_temp_location = f'{BASEDIR}/{img_filename}'
        img.save(img_temp_location)

        # Uploads file to our s3 bucket
        s3_client = boto3.client('s3')
        s3_client.upload_file(img_temp_location, S3_BUCKET, img_filename)

        # Makes the s3 image url public so that it is accessible to all clients
        s3_resource = boto3.resource('s3')
        object_acl = s3_resource.ObjectAcl(S3_BUCKET, img_filename)
        object_acl.put(ACL='public-read')

        os.remove(img_temp_location)

    def remove_from_aws(self):
        s3_client = boto3.client('s3')
        key = f'{self.salt}.{self.extension}'
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    watering_time = db.Column(db.Float, nullable=False)
    name = db.Column(db.String, nullable=False)
    time_elapsed = db.Column(db.Float, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    watering_date = db.Column(db.DateTime, nullable=False)
    creation_date = db.Column(db.DateTime, nullable=False)
    plant_tag = db.Column(db.String, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                        nullable=False)
    asset = db.relationship(
        'Asset', back_populates='plant', lazy=True, cascade='delete', uselist=False)
    user = db.relationship('User', back_populates='plants')

    def __init__(self, **kwargs):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.user_id = kwargs.get('user_id')
        self.watering_time = kwargs.get('watering_time')
        self.name = kwargs.get('name')
        self.plant_tag = kwargs.get('plant_tag')
        self.time_elapsed = 0
        self.start_time = now
        self.watering_date = self.start_time + \
            datetime.timedelta(milliseconds=self.watering_time)
        self.creation_date = now

    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'watering_time': self.watering_time,
            'name': self.name,
            'time_elapsed': self.time_elapsed,
            'start_time': str(self.start_time),
            'watering_date': str(self.watering_date),
            'creation_date': str(self.creation_date),
            'image': self.asset.return_url()
        }
