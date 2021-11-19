import base64
import boto3
import datetime
import os
import random
import re
import string
from user import *
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from io import BytesIO
from mimetypes import guess_extension, guess_type
from PIL import Image
from constants import EXTENSIONS, BASEDIR, S3_BUCKET, S3_BASE_URL

db = SQLAlchemy()


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

    def __init__(self, **kwargs):
        self._create(kwargs.get("image"))
        self.plant_id = kwargs.get('plant_id')

    def return_url(self):
        return f"{self.base_url}/{self.salt}.{self.extension}"

    def serialize(self):
        return {
            "url": f"{self.base_url}/{self.salt}.{self.extension}",
        }

    def _create(self, image_data):
        ext = guess_extension(guess_type(image_data)[0])[1:]
        if ext not in EXTENSIONS:
            raise Exception(f"Extension {ext} is not supported! :(")

        # Creates a random name to represent the image in our bucket
        salt = "".join(
            random.SystemRandom().choice(
                string.ascii_uppercase + string.digits
            )
            for _ in range(16)
        )

        # Extracts the image
        img_str = re.sub("^data:image/.+;base64,", "", image_data)
        img_data = base64.b64decode(img_str)
        img = Image.open(BytesIO(img_data))

        # Initializes our Asset
        self.base_url = S3_BASE_URL
        self.salt = salt
        self.extension = ext
        self.width = img.width
        self.height = img.height
        self.created_at = datetime.datetime.now()

        img_filename = f"{salt}.{ext}"
        self._upload(img, img_filename)

    def _upload(self, img, img_filename):
        img_temp_location = f"{BASEDIR}/{img_filename}"
        img.save(img_temp_location)

        # Uploads file to our s3 bucket
        s3_client = boto3.client('s3')
        s3_client.upload_file(img_temp_location, S3_BUCKET, img_filename)

        # Makes the s3 image url public so that it is accessible to all clients
        s3_resource = boto3.resource('s3')
        object_acl = s3_resource.ObjectACL(S3_BUCKET, img_filename)
        object_acl.put(ACL="public-read")

        os.remove(img_temp_location)


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    watering_time = db.Column(db.Float, nullable=False)
    name = db.Column(db.String, nullable=False),
    plant_tag = db.Column(db.String, nullable=False)
    time_elapsed = db.Column(db.Float, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    watering_date = db.Column(db.DateTime, nullable=False)
    creation_date = db.Column(db.DateTime, nullable=False)
    asset = db.relationship(
        'Asset', back_populates='plant', lazy=True, cascade='delete', uselist=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                        nullable=False)

    def __init__(self, **kwargs):
        now = datetime.now(datetime.timezone.utc)
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
            'plant_tag': self.plant_tag,
            'time_elapsed': self.time_elapsed,
            'start_time': str(self.start_time),
            'watering_date': str(self.watering_date),
            'creation_date': str(self.creation_date),
            'image': self.asset.return_url()
        }
