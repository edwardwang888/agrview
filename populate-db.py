import argparse
import subprocess
import csv
import pymysql.cursors
from datetime import datetime
import os

def parse_args():
    parser = argparse.ArgumentParser(description='Populate database with OO and GPS data.')
    parser.add_argument('--oo', help='input file containing OO data')
    parser.add_argument('--gps', help='input file containing GPS data')
    return parser.parse_args()

def populate_oo(args, connection):
    subprocess.run(['python3',os.getenv('OO_PARSER'),args.oo,'.'])
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

def populate_gps(args, connection):
    subprocess.run(['python3','gps_to_csv.py',args.gps])
    with open(args.gps + '.csv','r') as csvfile:
        csvreader = csv.reader(csvfile,delimiter=',')
        for row in csvreader:
            latitude = ('+' if row[3] == 'N' else '-') + row[2]
            longtitude = ('+' if row[5] == 'E' else '-') + row[4]
            print(latitude + ' ' + longtitude)
            with connection.cursor() as cursor:
                sql = "INSERT INTO `GPS` (`SysTime`,`GPSTime`,`Latitude`,`Longtitude`,`Altitude`,`GroundElevation`) VALUES(%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (row[0], row[1], latitude, longtitude, row[6], 0))

def main():
    args = parse_args()
    connection = pymysql.connect(host=os.getenv('MYSQL_INSTANCE'),
                             user=os.getenv('MYSQL_USER'),
                             password=os.getenv('MYSQL_PASSWORD'),
                             db=os.getenv('DB_NAME'),
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

    if args.oo != None:
        populate_oo(args, connection)

    if args.gps != None:
        populate_gps(args, connection)

    # Close connection to database
    connection.commit()
    connection.close()

if __name__ == "__main__":
    main()
