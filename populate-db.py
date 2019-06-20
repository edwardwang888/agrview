import argparse
import subprocess
import csv
import pymysql.cursors
from datetime import datetime
import os

def parse_args():
    parser = argparse.ArgumentParser(description='Populate database with OO data.')
    parser.add_argument('inputFile', help='input file containing OO data')
    return parser.parse_args()

def main():
    args = parse_args()
    subprocess.run(['python3',os.getenv('OO_PARSER'),args.inputFile,'.'])
    with open(os.getenv('OO_DIRECTORY') + 'timelist.txt','r') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        filelist = next(csvreader)
        csvfile.close()

    connection = pymysql.connect(host=os.getenv('MYSQL_INSTANCE'),
                             user=os.getenv('MYSQL_USER'),
                             password=os.getenv('MYSQL_PASSWORD'),
                             db=os.getenv('DB_NAME'),
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

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

    # Close connection to database
    connection.commit()
    connection.close()

if __name__ == "__main__":
    main()
