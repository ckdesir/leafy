import os

EXTENSIONS = ['png', 'gif', 'jpg', 'jpeg']
BASEDIR = os.getcwd()
S3_BUCKET = 'leafy-images'
S3_BASE_URL = f'https://{S3_BUCKET}.s3-us-east-1.amazonaws.com'
SECONDS_TO_MILLISECONDS_CONVERSION = 1000
