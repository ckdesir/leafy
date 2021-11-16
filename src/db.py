import base64
import boto3
import datetime
import os
import random
import re
import string
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

	def __init__(self, **kwargs):
		self.create(kwargs.get("image_data"))

	def serialize(self):
		return {
			"url": f"{self.base_url}/{self.salt}.{self.extension}",
		}

	def create(self, image_data):
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
		self.upload(img, img_filename)

	def upload(self, img, img_filename):
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