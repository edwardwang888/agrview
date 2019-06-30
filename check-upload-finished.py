import json
import boto3
import os

def lambda_handler(event, context):
    print(event)

    # Check if event has previous execution results
    try:
        numfiles = event['Input']['taskresult']['Payload']['Count']
        retries = event['Input']['taskresult']['Payload']['Retries']
    except KeyError:
        return {"Equal": False, "Count": 0, "Retries": 0}

    client = boto3.client('s3',
                      aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))

    # Count number of files for this particular prefix
    mybucket = os.getenv('MY_BUCKET')
    count = 0
    response = client.list_objects_v2(Bucket=mybucket, Prefix=event['Input']['Key'])
    count += response['KeyCount']
    while response['IsTruncated']:
        response = client.list_objects_v2(Bucket=mybucket, Prefix=event['Input']['Key'],
                                       ContinuationToken=response['NextContinuationToken'])
        count += response['KeyCount']

    return {"Equal": count == numfiles, "Count": count, "Retries": retries + 1}
