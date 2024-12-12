import boto3
import botocore
import numpy as np
import io

from PIL import Image

import config as cnfg

class ObjectStorage(object):
    def __init__(self):
        self.s3 = boto3.client(
            service_name = 's3',
            aws_access_key_id = cnfg.S3_ID_KEY,
            aws_secret_access_key = cnfg.S3_SECRET_KEY,
            endpoint_url = "https://storage.yandexcloud.net"
        )
        self.bucket_name = cnfg.S3_BUCKET_NAME


    def file_exists(self, file_name):
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=file_name)
            return True
        except botocore.exceptions.ClientError:
            return False

    def get_img(self, name, path):
        if (name is None) or (path is None):
            return None
        path = path + "/" + name
        if self.file_exists(path):
            file = self.s3.get_object(Bucket=self.bucket_name, Key=path)
            image_bytes = file['Body'].read()
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            return np.array(image)
        else:
            return None

    def get_sqlite_file(self):
        name = cnfg.DB_NAME
        if self.file_exists(name):
            self.s3.download_file(Bucket=self.bucket_name, Key=name, Filename=name)
            return