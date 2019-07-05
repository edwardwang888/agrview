import argparse
import subprocess
import csv
import pymysql.cursors
from datetime import datetime
import boto3
import botocore.config
import urllib.parse
import json
import os
import math

print('Loading function')
client = boto3.client('s3',
                      aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))
s3 = boto3.resource('s3',
                    aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))

def parse_args():
    """
    Parses command line arguments if called from the command line. This function is not
    invoked when run as a Lambda function.
    """
    parser = argparse.ArgumentParser(description='Populate database with OO and GPS data.')
    parser.add_argument('--oo', help='input file containing OO data')
    parser.add_argument('--gps', help='input file containing GPS data')
    return parser.parse_args()

def connectDB():
    """
    Returns a connection to the MySQL database specified by the environmental variables
    configured in the Lambda function.
    """
    return pymysql.connect(host=os.getenv('MYSQL_INSTANCE'),
                             user=os.getenv('MYSQL_USER'),
                             password=os.getenv('MYSQL_PASSWORD'),
                             db=os.getenv('DB_NAME'),
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

def populate_oo(connection, oo_file, numseconds):
    """
    Parses OO data and checks if the number of readings is consistent with the number of seconds of flight.
    The seconds of flight is determined previously and passed in as a parameter.
    """
    # Download OO file from S3 bucket
    print('oo_file: {}'.format(oo_file))
    s3.meta.client.download_file(os.getenv('MY_BUCKET1'), oo_file, '/tmp/oo_file.txt')

    # Run OO parser
    subprocess.run(['python3',os.getenv('OO_PARSER'),'/tmp/oo_file.txt','/tmp'])
    print('Finished parsing OO data')
    with open(os.getenv('OO_DIRECTORY') + 'timelist.txt','r') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        filelist = next(csvreader)
        csvfile.close()

    # Check number of OO readings
    if math.fabs(numseconds - len(filelist)) > 1000:
        print('OO readings: {}'.format(len(filelist)))
        raise Exception('Number of OO readings inconsistent with duration of flight')

    # Parse OO data and populate into database; eventually may want to remove
    # filelist and look for files directly.
    for filename in filelist:
        if filename != "":
            with open(os.getenv('OO_DIRECTORY') + filename + '.txt') as f:
                systime = f.readline().split(' : ')[2].strip()
                systime = datetime.strptime(systime,'%a %b %d %H:%M:%S %Y').strftime('%Y-%m-%d %H:%M:%S')
                datarow = f.readline().split(' : ')[2].split(sep=',', maxsplit=1)
                oo_key2_data = datarow[0]
                oo_key3_data = datarow[1]

            with connection.cursor() as cursor:
                sql = "INSERT INTO `" + os.getenv('OO_TABLE') + "` (`SysTime`,`" + \
                      os.getenv('OO_KEY2') + "`,`" + os.getenv('OO_KEY3') + "`) VALUES(%s, %s, %s)"
                cursor.execute(sql, (systime, oo_key2_data, oo_key3_data))

    print('Finished populating OO')

def populate_gps(connection, gps_file):
    """
    Populates GPS data and gets the number of seconds of flight from the first and last GPS readings.
    Returns the number of seconds for use in further data validation.
    """
    # Download GPS file from S3 bucket
    dest = '/tmp/' + os.path.basename(gps_file)
    s3.meta.client.download_file(os.getenv('MY_BUCKET1'), gps_file, dest)

    # Run GPS parser
    print(subprocess.run(['python3','gps_to_csv.py',dest],stdout=subprocess.PIPE,stderr=subprocess.PIPE))
    print('Finished running GPS parsing')

    # Parse GPS readings and populate them into the database; additionally, count
    # the number of GPS readings and keep track of the first and last timestamps.
    with open(dest + '.csv','r') as csvfile:
        csvreader = csv.reader(csvfile,delimiter=',')
        next(csvreader)
        mindate = None
        maxdate = None
        count = 0
        for row in csvreader:
            count += 1
            latitude = ('+' if row[3] == 'N' else '-') + row[2]
            longtitude = ('+' if row[5] == 'E' else '-') + row[4]
            systime = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f')
            if mindate == None or systime < mindate:
                mindate = systime
            if maxdate == None or systime > maxdate:
                maxdate = systime
            with connection.cursor() as cursor:
                sql = "INSERT INTO `GPS` (`SysTime`,`GPSTime`,`Latitude`,`Longtitude`,`Altitude`,`GroundElevation`) VALUES(%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (row[0], row[1], latitude, longtitude, row[6], row[7]))

        print('Min date is:')
        print(mindate)
        print('Max date is:')
        print(maxdate)
        print('Total elapsed time is:')
        difference = maxdate - mindate
        print(difference)
        numseconds = difference.total_seconds()
        print('Seconds elapsed is:')
        print(numseconds)
        print('Number of GPS readings:')
        print(count)

        # Check number of GPS readings
        if math.fabs(numseconds - count) > 1000:
            raise Exception('Number of GPS readings inconsistent with flight duration')
        return numseconds

def lambda_handler(event, context):
    """
    Main Lambda handler function that populates the raw data into the database and also
    validates some file counts that are passed into the function from a previous step
    of the state machine.
    """
    # Log the received event
    print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event
    key = event['Input']['Key']
    print('Key: {}'.format(key))

    # Check that key contains flight code; otherwise do nothing
    if key[-5:-1].isalpha():
        # Connect to database
        connection = connectDB()
        print('Connection successful!')

        # Check for missing files and throw exception if any are missing.
        # NOTE: this should never throw an exception since file checking is done
        # in previous steps of the state machine.
        missing_files = []
        try:
            oo_file = client.list_objects(Bucket = os.getenv('MY_BUCKET1'),
                                                    Prefix = key + os.getenv('OO_FILEPATH'))['Contents'][0]['Key']
        except KeyError:
            missing_files.append(key + os.getenv('OO_FILEPATH'))

        try:
            gps_file = client.list_objects(Bucket=os.getenv('MY_BUCKET1'),Prefix=key+'gps')['Contents'][0]['Key']
        except KeyError:
            missing_files.append('key' + gps)

        if len(missing_files) != 0:
            raise FileNotFoundError('The following keys were missing: {}'.format(missing_files))

        # Print file names for logging
        print('oo file: {}'.format(oo_file))
        print('gps file: {}'.format(gps_file))

        # Populate GPS and OO data and store the number of seconds of flight returned by populate_gps()
        numseconds = populate_gps(connection, gps_file)
        populate_oo(connection, oo_file, numseconds)

        # Check HCount and ICount to verify they are consistent with flight duration
        hcount = event['Input']['taskresult']['Payload']['HCount']
        icount = event['Input']['taskresult']['Payload']['ICount']
        print('HCount: {}'.format(hcount))
        print('ICount: {}'.format(icount))
        if math.fabs(hcount - numseconds) > 1000:
            raise Exception('Number of H Images inconsistent with flight duration')
        if math.fabs(icount - 10 * numseconds) > 10000:
            raise Exception('Number of I Images inconsistent with flight duration')

        # Populate FlightLookup table
        data = key.split('/')
        print('Now populating FlightLookup')
        with connection.cursor() as cursor:
                sql = "INSERT INTO `FlightLookup` (`" + os.getenv('FLIGHT_KEY1') + \
                      "`,`" + os.getenv('FLIGHT_KEY2') + \
                      "`,`FlightDate`,`FlightCode`) VALUES(%s, %s, %s, %s)"
                cursor.execute(sql, ('s3://' + os.getenv('MY_BUCKET1') + '/' + key,
                                     's3://' + os.getenv('MY_BUCKET2') + '/' + key,
                                     data[0], data[1]))
                print('Finished populating FlightLookup')

        connection.commit()
        connection.close()

def main():
    args = parse_args()
    connection = connectDB()

    if args.oo != None:
        populate_oo(connection, args.oo)

    if args.gps != None:
        populate_gps(connection, args.gps)

    # Close connection to database
    connection.commit()
    connection.close()

if __name__ == "__main__":
    main()
