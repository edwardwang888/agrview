import json
import os
import boto3

def lambda_handler(event, context):
    client = boto3.client('s3',
                      aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))
    type = event['Type']
    key = event['Key']

    # Attempt to list the specified files; if the file(s) do not exist, an exception will occur
    if type == 'GPS':
        client.list_objects(Bucket=os.getenv('MY_BUCKET'),Prefix=key+'gps')['Contents'][0]['Key']
        return key + 'gps'
    elif type == 'OFile':
        client.list_objects(Bucket = os.getenv('MY_BUCKET'),
                            Prefix = key + os.getenv('OFILE1'))['Contents'][0]['Key']
        client.list_objects(Bucket = os.getenv('MY_BUCKET'),
                            Prefix = key + os.getenv('OFILE2'))['Contents'][0]['Key']
        return os.getenv('OFILE1')
    elif type == 'IFile':
        client.list_objects(Bucket = os.getenv('MY_BUCKET'),
                            Prefix = key + os.getenv('IFILE1'))['Contents'][0]['Key']
        client.list_objects(Bucket = os.getenv('MY_BUCKET'),
                            Prefix = key + os.getenv('IFILE2'))['Contents'][0]['Key']
        return [os.getenv('IFILE1'), os.getenv('IFILE2')]
