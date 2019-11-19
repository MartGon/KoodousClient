
from KoodousApiClient import *
from SQL3Client import *

import argparse
import sqlite3
import os

def main():
    
    # Config arg parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--token', '-t', help = 'Koodous API Token', required=True)
    argparser.add_argument('--search', '-s', help = 'Koodous search string', required=True)
    
    database = argparser.add_argument_group('database')
    
    database.add_argument('--database-file', '-dbf', help = 'SQLite3 database file location', required=False)
    
    download = argparser.add_argument_group('download')
    
    download.add_argument('--dest-folder', '-df', help = 'Download destination folder', required=False)
    
    # Parse arguments
    args = argparser.parse_args()
    
    # Get data
    
        # Mandatory
    token = args.token
    search_param = args.search
    
        # Optional
    database_file = os.path.abspath(args.database_file) if args.database_file else None
    dest_folder = os.path.abspath(args.dest_folder) if args.dest_folder else None
    
    # Init database
    dbclient = NullSQL3Client()
    if database_file:
        print(len(database_file))
        dbclient = SQL3Client()
        
    dbclient.connect(database_file)
    
    #cursor.execute('''DROP TABLE tags''')
    #cursor.execute('''DROP TABLE apks''')
    
        # Create Tables
    dbclient.execute('''CREATE TABLE IF NOT EXISTS apks (package_name char(255), sha256 char(255) PRIMARY KEY, path char(255), malware BOOL) ''')
    dbclient.execute('''CREATE TABLE IF NOT EXISTS tags (id int PRIMARY KEY, info UNIQUE)''')
    dbclient.execute('''CREATE TABLE IF NOT EXISTS apk_tags (sha256, tag)''')
    
        # Commit changes
    dbclient.commit()
    
    # Create Api client 
    client = KoodousApiClient(token)
    
    # Search request
    resp = client.search_koodous_db(search_param)
    results = resp.json()['results']
    
    #print(resp.json())
    print("Results found: " + str(len(results)))
    
    # Create apk dictionaries
    apks = []
    for result in results:
        if not result['corrupted']:
            apk = {}
            apk['name'] = result['app']
            apk['package_name'] = result['package_name']
            apk['sha256'] = result['sha256']
            apk['tags'] = result['tags']
            apk['malware'] = True
            print(apk)
            
            apks.append(apk)
        
    print("Valid APKs data found: " + str(len(apks)))    
    
    # Download apks
    if dest_folder:        
        for apk in apks:
            apk['path'] = os.path.join(dest_folder, apk['sha256'][:16] + ".apk")
            client.download(apk['sha256'], apk['path'])
    
    # Save apk data into database 
    for apk in apks:
        dbclient.execute("insert or replace into apks (package_name, sha256, path, malware) values(:package_name, :sha256, :path, :malware)", apk)
    
        # Commit changes
    dbclient.commit()
    
    dbclient.close()

if __name__ == '__main__':
    main()