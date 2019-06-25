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

print('Loading function')
client = boto3.client('s3',
                      aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))
s3 = boto3.resource('s3',
                    aws_access_key_id=os.getenv('MY_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('MY_SECRET_ACCESS_KEY'))

def parse_args():
    parser = argparse.ArgumentParser(description='Populate database with OO and GPS data.')
    parser.add_argument('--oo', help='input file containing OO data')
    parser.add_argument('--gps', help='input file containing GPS data')
    return parser.parse_args()

def connectDB():
    return pymysql.connect(host=os.getenv('MYSQL_INSTANCE'),
                             user=os.getenv('MYSQL_USER'),
                             password=os.getenv('MYSQL_PASSWORD'),
                             db=os.getenv('DB_NAME'),
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

def populate_oo(connection, oo_file):
    print('oo_file: {}'.format(oo_file))
    s3.meta.client.download_file(os.getenv('MY_BUCKET1'), oo_file, '/tmp/oo_file.txt')
    subprocess.run(['python3',os.getenv('OO_PARSER'),'/tmp/oo_file.txt','/tmp'])
    print('Finished parsing OO data')
    with open(os.getenv('OO_DIRECTORY') + 'timelist.txt','r') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        filelist = next(csvreader)
        csvfile.close()

    # Eventually may want to remove filelist and look for files directly
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
    dest = '/tmp/' + os.path.basename(gps_file)
    s3.meta.client.download_file(os.getenv('MY_BUCKET1'), gps_file, dest)
    print(subprocess.run(['python3','gps_to_csv.py',dest],stdout=subprocess.PIPE,stderr=subprocess.PIPE))
    print('Finished running GPS parsing')
    with open(dest + '.csv','r') as csvfile:
        csvreader = csv.reader(csvfile,delimiter=',')
        next(csvreader)
        for row in csvreader:
            latitude = ('+' if row[3] == 'N' else '-') + row[2]
            longtitude = ('+' if row[5] == 'E' else '-') + row[4]
            with connection.cursor() as cursor:
                sql = "INSERT INTO `GPS` (`SysTime`,`GPSTime`,`Latitude`,`Longtitude`,`Altitude`,`GroundElevation`) VALUES(%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (row[0], row[1], latitude, longtitude, row[6], row[7]))

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    print('Key: {}'.format(key))

    # Check that key contains flight code
    if key[-5:-1].isalpha():
        connection = connectDB()
        print('Connection successful!')
        oo_file = key + os.getenv('OO_FILEPATH')
        print('oo file: {}'.format(oo_file))
        gps_file = client.list_objects(Bucket=os.getenv('MY_BUCKET1'),Prefix=key+'gps')['Contents'][0]['Key']
        print('gps file: {}'.format(gps_file))

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

        populate_oo(connection, oo_file)
        populate_gps(connection, gps_file)
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
