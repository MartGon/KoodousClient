from DatasetMgr.KoodousDownloader import *
from DatasetMgr.FeatureMgr import *
from DatasetMgr.GoodwareDownloader import *

import argparse
import sqlite3
import os

MAX_DOWNLOAD_PER_DAY = 50
SQL_DB_CONFIG_FILE = "dbconfig.sql"  
        
def main():
    
    # Config arg parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--tokens', '-t', help = 'Koodous API Token', required=False, nargs='+')
    argparser.add_argument('--search', '-s', help = 'Koodous search string', required=False)
    argparser.add_argument('--quantity', '-q', help = 'Amount of apps to search/download', required=False, type=int) 
    argparser.add_argument('--is-malware', '-iw', help = 'Whether to consider the result apks as malware', required=False, type=int, default=1)
    
    database = argparser.add_argument_group('database')
    database.add_argument('--database-file', '-dbf', help = 'SQLite3 database file location', required=False)
    database.add_argument('--update-db', '-udb', help = 'Update provided database file with already downloaded apks', required = False, type=bool, default=False)
    
    download = argparser.add_argument_group('download')
    download.add_argument('--dest-folder', '-df', help = 'Download destination folder', required=False)
    
    # Parse arguments
    args = argparser.parse_args()
    
    # Get data
        # Mandatory
    tokens = args.tokens if args.tokens is not None else ["null"]
    search_param = args.search
    
        # Optional
    quantity = args.quantity if args.quantity is not None else 50
    is_malware = args.is_malware
    database_file = os.path.abspath(args.database_file) if args.database_file else None
    dest_folder = os.path.abspath(args.dest_folder) if args.dest_folder else None
    update_db = args.update_db
    
    # Search request
    if search_param:
    
            # Create Api client 
        if is_malware:   
            downloader = KoodousDatasetDownloader(tokens)
        else:
            downloader = GooglePlayDownloader()
    
        apks = downloader.search(search_param, quantity)
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
                
                downloader = KoodousDatasetDownloader(tokens)
                
                # Connect to database
                downloader.connect_db(database_file)
                
                # Create feature_mgr
                feature_mgr = FeatureManager()
                feature_mgr.connect_db(database_file)
                
                # Update database with apks already downloaded
                if update_db:
                    rowcount = downloader.update_db(dest_folder)
                    print("%s downloaded rows successfully updated" % rowcount)
                    
                    rowcount = feature_mgr.update_db(dest_folder)
                    print("%s apk features updated" % rowcount)
                    
                # Get apks not yet downloaded
                elif is_malware:    
                    results = downloader.search_db('''Select sha256, filename from apks where downloaded=0 AND download_failed=0''')
                    print("Found %i download candidates" % len(results))
                    
                    download_amount = 0
                    print("Download Progress 00%")
                    for apk in results:
                        print("Trying to download %s" % apk['sha256'])
                            
                        try:
                        
                            if downloader.download_apk(dest_folder, apk):
                            
                                # Increase download count
                                download_amount = download_amount + 1
                                percent = round(download_amount / quantity, 2) * 100 
                                print("\rDownload Progress %i" % percent)
                                
                                # Extract and save features
                                apk_path = os.path.join(dest_folder, apk['filename'])
                                apk_features = feature_mgr.extract_features(apk_path)
                                feature_mgr.save_features(apk_features, apk['filename'])
                               
                        except DownloadException:
                            print("Exception: DownloadException caught")
                            break
                            
                    print("%i Apps Downloaded" % download_amount)
                
                # Disconnect from DB
                downloader.disconnect_db()
                feature_mgr.disconnect_db()
                    
            else:
                argparser.error("Missing database_file")
            
        else:
            argparser.error("Missing dest_folder")

if __name__ == '__main__':
    main()