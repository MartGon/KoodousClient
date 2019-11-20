
from KoodousApiClient import *
from SQL3Client import *

import argparse
import sqlite3
import os

MAX_DOWNLOAD_PER_DAY = 50
SQL_DB_CONFIG_FILE = "dbconfig.sql"

def main():
    
    # Config arg parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--token', '-t', help = 'Koodous API Token', required=True)
    argparser.add_argument('--search', '-s', help = 'Koodous search string', required=False)
    argparser.add_argument('--quantity', '-q', help = 'Amount of apps to search/download', required=False, type=int) 
    
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
    quantity = args.quantity
    database_file = os.path.abspath(args.database_file) if args.database_file else None
    dest_folder = os.path.abspath(args.dest_folder) if args.dest_folder else None
    
    # Create Api client 
    client = KoodousApiClient(token)
    
    # Search request
    if search_param:
        results = client.search_koodous_db(search_param, quantity)
        
        print("Results found: " + str(len(results)))
        
        # Create apk dictionaries
        apks = []
        for result in results:
            if not result['corrupted']:
                apk = {}
                apk['package_name'] = result['package_name']
                apk['sha256'] = result['sha256']
                apk['filename'] = apk['sha256'][:16] + ".apk"
                apk['tags'] = result['tags']
                apk['malware'] = True
                print(apk)
                
                apks.append(apk)
            
        print("Valid APKs data found: " + str(len(apks)))    
        
         # Search and Database
        if database_file:
        
            # Connect to database
            dbclient = SQL3Client()
            exists = os.path.exists(database_file)
            dbclient.connect(database_file)
            
            # Init databse
            if not exists:
                print("Warning: Database doesn't exist, initializing...")
                statements = open(SQL_DB_CONFIG_FILE, 'r').read().split('\n')
                for statement in statements:
                    dbclient.execute(statement)
                dbclient.commit()
                
        
            for apk in apks:
                dbclient.execute("insert or replace into apks (package_name, filename, sha256, malware) values(:package_name, :filename, :sha256, :malware)", apk)
                
                for tag in apk['tags']:
                    dbclient.execute("insert or ignore into tags (info) values(:tag)", {'tag': tag})   
                    dbclient.execute('''select id from tags where info = :tag''', {'tag' : tag})
                    id = dbclient.fetchone()[0]
                    dbclient.execute("insert or replace into apk_tags(apk, tag) values(?,?)", [apk['sha256'], id])
            
                # Commit changes
            dbclient.commit()
            dbclient.close()
        
            # Search, Database and Download
            if dest_folder:        
            
                download_amount = 0
                for apk in apks:
                
                    if download_amount == MAX_DOWNLOAD_PER_DAY:
                        print("Maximum download amount per day reached, skipping")
                        break
                    
                    if not os.path.exists(path):
                        path = os.path.join(dest_folder, apk['filename'])
                        client.download(apk['sha256'], path)
                        
                        download_amount = download_amount + 1
                    # File exists
                    else:
                        print("Warning: File with same name already exists. Download aborted")
                    
    # No Search, Download and Database         
    else:
        
        # Download request
        if dest_folder:        
            
            if database_file:
            
                # Connect to database
                dbclient = SQL3Client()
                dbclient.connect(database_file)
                
                # Get apks not yet downloaded
                dbclient.execute('''Select sha256, filename from apks where downloaded=0''')
                results = dbclient.fetchall()
               
                print("Found %i download candidates" % len(results))
                
                download_amount = 0
                for apk in results:
                    sha256 = apk[0]
                    filename = apk[1]
                
                    if download_amount == quantity:
                        print("Selected download amount reached, aborting")
                        break
                
                    if download_amount == MAX_DOWNLOAD_PER_DAY:
                        print("Maximum download amount per day reached, skipping")
                        break
                    
                    path = os.path.join(dest_folder, filename)
                    if not os.path.exists(path):
                        #client.download(apk[0], path)
                        
                        if os.path.exists(path):
                            dbclient.execute('''Update apks SET downloaded = 1 where sha256=:sha256''', {'sha256' : sha256})
                            download_amount = download_amount + 1
                        else:
                            print("Error: Download of %s failed" % filename)
                    # File exists
                    else:
                        print("Warning: File with same name already exists. Download aborted")
                        
                print("%i Apps Downloaded" % download_amount)
                        
                dbclient.commit()
                dbclient.close()
            
        else:
            argparser.error("Missing dest_folder")

if __name__ == '__main__':
    main()