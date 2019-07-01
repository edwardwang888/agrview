import json
import boto3
import os
from datetime import datetime, timezone

def get_latest_date(response):
    latest_date = None
    for entry in response['Contents']:
        if latest_date == None or entry['LastModified'] > latest_date:
            latest_date = entry['LastModified']

    return latest_date

def lambda_handler(event, context):
    print(event)

    client = boto3.client('s3',
                      aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))
    mybucket = os.getenv('MY_BUCKET')
    response = client.list_objects_v2(Bucket=mybucket, Prefix=event['Input']['Key'])
    latest_date = get_latest_date(response)
    while response['IsTruncated']:
        response = client.list_objects_v2(Bucket=mybucket, Prefix=event['Input']['Key'],
                                       ContinuationToken=response['NextContinuationToken'])
        new_date = get_latest_date(response)
        if new_date > latest_date:
            latest_date = new_date

    print('Latest datetime is: {}'.format(latest_date))
    print('Current datetime is: {}'.format(datetime.now(timezone.utc)))
    if (datetime.now(timezone.utc) - latest_date).total_seconds() > 18000:
        return {"Done": True, "Retries": 0}
    else:
        try:
            retries = event['Input']['taskresult']['Payload']['Retries']
        except KeyError:
            retries = 1
        return {"Done": False, "Retries": retries + 1}
