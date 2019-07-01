import json
import boto3
import os
from datetime import datetime, timezone

def traverse_files(response):
    """
    Finds the latest modification date of all files in the response
    and counts the number of files for two image types. The image types
    are obscured for confidentiality reasons.
    """
    latest_date = None
    count1 = 0
    count2 = 0
    for entry in response['Contents']:
        if latest_date == None or entry['LastModified'] > latest_date:
            latest_date = entry['LastModified']
        if os.getenv('IMAGE_TYPE1') in entry['Key']:
            count1 += 1
        elif os.getenv('IMAGE_TYPE2') in entry['Key']:
            count2 += 1

    return {"latest_date": latest_date, "count1": count1, "count2": count2}

def lambda_handler(event, context):
    print(event)
    key = event['Input']['Key']
    client = boto3.client('s3',
                      aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))
    mybucket = os.getenv('MY_BUCKET')
    response = client.list_objects_v2(Bucket=mybucket, Prefix=key)
    output = traverse_files(response)
    latest_date = output['latest_date']
    count1 = output['count1']
    count2 = output['count2']
    while response['IsTruncated']:
        response = client.list_objects_v2(Bucket=mybucket, Prefix=key,
                                       ContinuationToken=response['NextContinuationToken'])
        output = traverse_files(response)
        new_date = output['latest_date']
        count1 += output['count1']
        count2 += output['count2']
        if new_date > latest_date:
            latest_date = new_date

    print('Latest datetime is: {}'.format(latest_date))
    print('Current datetime is: {}'.format(datetime.now(timezone.utc)))
    if (datetime.now(timezone.utc) - latest_date).total_seconds() > 18000:
        return {"Done": True, "Retries": 0, "HCount": count1, "ICount": count2}
    else:
        try:
            retries = event['Input']['taskresult']['Payload']['Retries']
        except KeyError:
            retries = 1
        return {"Done": False, "Retries": retries + 1}
