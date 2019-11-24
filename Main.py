
from KoodousApiClient import *
from SQL3Client import *

import argparse
import sqlite3
import os

MAX_DOWNLOAD_PER_DAY = 50
SQL_DB_CONFIG_FILE = "dbconfig.sql"

class KoodousDatasetDownloader:

    dbclient = None
    
    def __init__(self, token):
        self.apiclient = KoodousApiClient(token)

    def search_koodous(self, search_param, quantity=50, is_malware=True):
        
        results = self.apiclient.search_koodous_db(search_param, quantity)
        
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
                apk['malware'] = is_malware
                #print(apk)
                
                apks.append(apk)
        
        return apks
    
    def search_db(self, search_param, *args):
            
        if self.dbclient is None:
            raise Exception("Not Connected to DB. Cannot search db!")    
            
        self.dbclient.execute(search_param, *args)
        return self.dbclient.fetchall()
    
    def connect_db(self, database_file):
        
        # Connect to database
        self.dbclient = SQL3Client()
        exists = os.path.exists(database_file)
        self.dbclient.connect(database_file)
        
        # Init databse
        if not exists:
            print("Warning: Database doesn't exist, initializing...")
            db_config_path = os.path.join(os.path.dirname(__file__), SQL_DB_CONFIG_FILE)
            statements = open(db_config_path, 'r').read().split('\n')
            for statement in statements:
                self.dbclient.execute(statement)
            self.dbclient.commit()
        
    def disconnect_db(self):
        
        self.dbclient.commit()
        self.dbclient.close()
    
    def save_apk(self, apk):
    
        if self.dbclient is None:
            raise Exception("Not Connected to DB. Cannot save apk!")
    
        self.dbclient.execute("insert or replace into apks (package_name, filename, sha256, malware) values(:package_name, :filename, :sha256, :malware)", apk)
        
        for tag in apk['tags']:
            self.dbclient.execute("insert or ignore into tags (info) values(:tag)", {'tag': tag})   
            self.dbclient.execute('''select id from tags where info = :tag''', {'tag' : tag})
            id = self.dbclient.fetchone()[0]
            self.dbclient.execute("insert or replace into apk_tags(apk, tag) values(?,?)", [apk['sha256'], id])
            
        self.dbclient.commit()
            
    def download_apk(self, dest_folder, apk):
    
        if self.dbclient is None:
            raise Exception("Not Connected to DB. Cannot download apk!")
    
        sha256 = apk['sha256']
        filename = apk['filename']
        result = False
        
        path = os.path.join(dest_folder, filename)
        if not os.path.exists(path):
            result = self.apiclient.download(sha256, path)

            if result == 200:
                if os.path.exists(path):
                    print("Info: Download was succesful")
                    self.dbclient.execute('''Update apks SET downloaded = 1 where sha256=:sha256''', {'sha256' : sha256})
                    self.dbclient.commit()
                    result = True
                else:
                    print("Error: Download of %s failed" % filename)
                    result = False
            elif result == 404:
                print("Error: Could not download from this server, updated download failed flag")
                self.dbclient.execute('''Update apks SET download_failed = 1 where sha256=:sha256''', {'sha256' : sha256})
                self.dbclient.commit()
                result = False
            elif result == 429:
                print("Error: Download failed. Max Daily download rate reached")
                result = False
            elif result == 430:
                print("Error: No more tokens left")  
                result = False
        # File exists
        else:
            print("Warning: File with same name already exists. Download aborted")
            result = False
            
        return result
        
    def update_db(self, dest_folder):
    
        if self.dbclient is None:
            raise Exception("Not Connected to DB. Cannot update db!")
            
        apks = [f for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk in apks:
            self.dbclient.execute('''Update apks set downloaded = 1 where filename=:filename''', {'filename' : apk})
            rowcount =  rowcount + self.dbclient.cursor.rowcount
            
        self.dbclient.commit()
        
        return rowcount
        
        
def main():
    
    # Config arg parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--tokens', '-t', help = 'Koodous API Token', required=True, nargs='+')
    argparser.add_argument('--search', '-s', help = 'Koodous search string', required=False)
    argparser.add_argument('--quantity', '-q', help = 'Amount of apps to search/download', required=False, type=int) 
    argparser.add_argument('--is-malware', '-iw', help = 'Whether to consider the result apks as malware', required=False, type=bool, default=True)
    
    database = argparser.add_argument_group('database')
    database.add_argument('--database-file', '-dbf', help = 'SQLite3 database file location', required=False)
    database.add_argument('--update-db', '-udb', help = 'Update provided database file with already downloaded apks', required = False, type=bool, default=False)
    
    download = argparser.add_argument_group('download')
    download.add_argument('--dest-folder', '-df', help = 'Download destination folder', required=False)
    
    # Parse arguments
    args = argparser.parse_args()
    
    # Get data
        # Mandatory
    tokens = args.tokens
    search_param = args.search
    
        # Optional
    quantity = args.quantity if args.quantity is not None else 50
    is_malware = args.is_malware
    database_file = os.path.abspath(args.database_file) if args.database_file else None
    dest_folder = os.path.abspath(args.dest_folder) if args.dest_folder else None
    update_db = args.update_db
    
    # Create Api client 
    downloader = KoodousDatasetDownloader(tokens)
    
    # Search request
    if search_param:
        apks = downloader.search_koodous(search_param, quantity)
        print("Valid APKs data found: " + str(len(apks)))    
        
         # Search and Database
        if database_file:
        
            # Connect to database
            downloader.connect_db(database_file)
        
            for apk in apks:
                downloader.save_apk(apk)
        
            # Search, Database and Download
            if dest_folder:        
                for apk in apks:
                    downloader.download_apk(dest_folder, apk)
                        
            downloader.disconnect_db()
            
        else:
            for apk in apks:
                print(apk)
                    
    # No Search, Download and Database         
    else:
        
        # Download request
        if dest_folder:        
            
            if database_file:
                
                # Connect to database
                downloader.connect_db(database_file)
                
                # Update database with apks already downloaded
                if update_db:
                    rowcount = downloader.update_db(dest_folder)
                    
                    print("%s rows successfully updated" % rowcount)
                # Get apks not yet downloaded
                else:    
                    results = downloader.search_db('''Select sha256, filename from apks where downloaded=0 AND download_failed=0''')
                    print("Found %i download candidates" % len(results))
                    
                    download_amount = 0
                    print("Download Progress 00%")
                    for apk in results:
                        print("Trying to download %s" % apk['sha256'])
                        sha256 = apk['sha256']
                        filename = apk['filename']
                    
                        if download_amount == quantity:
                            print("Selected download amount reached, aborting")
                            break
                        try:
                            if downloader.download_apk(dest_folder, apk):
                                download_amount = download_amount + 1
                                percent = round(download_amount / quantity, 2) * 100 
                                print("\rDownload Progress %i" % percent)
                        except DownloadException:
                            print("Exception: DownloadException caught")
                            break
                            
                            
                    print("%i Apps Downloaded" % download_amount)
                            
                downloader.disconnect_db()
                    
            else:
                argparser.error("Missing database_file")
            
        else:
            argparser.error("Missing dest_folder")

if __name__ == '__main__':
    main()