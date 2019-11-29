from DatasetMgr.KoodousDownloader import *
from DatasetMgr.FeatureMgr import *
from DatasetMgr.GoodwareDownloader import *
from DatasetMgr.DBDatasetUpdater import *

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
    download.add_argument('--gplaycli-conf', '-gp', help = 'GooglePlayCLI config file', required=False)


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
    do_update_db = args.update_db
    gplaycli_conf = args.gplaycli_conf
    
    # Search request
    if search_param:
    
        # Create Api client by goodware or malware
        downloader = None
        if is_malware:   

            # Require token for malware searches
            if "null" in tokens:
                argparser.error("Token argument is needed for searchs")

            downloader = KoodousDatasetDownloader(tokens)
        else:

            if gplaycli_conf is None:
                argparser.error("GPlayCli conf file is needed to download beningware")

            downloader = GooglePlayDownloader(gplaycli_conf)
    
        # Perform a search
        apks = downloader.search(search_param, quantity)
        print("Valid APKs data found: " + str(len(apks)))    
        
         # Search and Database
        if database_file:

            # Save apk found data in DB
            save_apks(downloader, apks, database_file)
        
            # Search, Database and Download
            if dest_folder:        
                # Download apks
                download_apks(downloader = downloader, tokens = tokens, database_file = database_file, apks = apks, dest_folder =dest_folder)

                # Extract features
                extract_features(apks = apks, database_file = database_file, dest_folder = dest_folder)

        # Print results
        else:
            for apk in apks:
                print(apk)

    # No Search, Download and Database         
    else:
        
        # Download request
        if dest_folder:        
            
            if database_file:
                
                # Update database with apks already downloaded
                if do_update_db:
                    update_db(database_file, dest_folder)
                    
                # Get apks marked for download in DB
                else:
                    
                    # Download only malware
                    if is_malware:  
                        # Create Api client by goodware or malware
                        downloader = KoodousDatasetDownloader(tokens)

                        # Search for download canditates
                        results = downloader.search_db('''Select sha256, filename from apks where downloaded=0 AND download_failed=0''')
                        print("Found %i download candidates" % len(results))
                        
                        # Download apks
                        download_apks(downloader = downloader, tokens = tokens, database_file = database_file, apks = results, dest_folder = dest_folder)

                        # Extract features
                        extract_features(apks = results, database_file = database_file, dest_folder = dest_folder)
                    
            else:
                argparser.error("Missing database_file")
            
        else:
            argparser.error("Missing dest_folder")


def save_apks(downloader, apks, database_file):

    #  Connect to DB
    downloader.connect_db(database_file)

    for apk in apks:
        downloader.save_apk(apk)

    # Disconnect from DB
    downloader.disconnect_db()

def download_apks(downloader, tokens, database_file, apks, dest_folder):

    #  Connect to DB
    downloader.connect_db(database_file)
    
    download_amount = 0
    print("Download Progress 00%")
    for apk in apks:
        print("Trying to download %s" % apk['filename'])
            
        try:
            if downloader.download_apk(dest_folder, apk):
            
                # Increase download count
                download_amount = download_amount + 1
                percent = round(download_amount / quantity, 2) * 100 
                print("\rDownload Progress %i" % percent)
                
        except DownloadException:
            print("Exception: DownloadException caught")
            break
            
    print("%i Apps Downloaded" % download_amount)

    # Disconnect from DB
    downloader.disconnect_db()

def extract_features(apks, database_file, dest_folder):

    # Create feature_mgr
    feature_mgr = FeatureManager()
    feature_mgr.connect_db(database_file)

    for apk in apks:
         # Extract and save features
        apk_path = os.path.join(dest_folder, apk['filename'])

        if os.path.exists(apk_path):
            apk_features = feature_mgr.extract_features(apk_path)
            feature_mgr.save_features(apk_features, apk['filename'])

    # Disconnect from DB
    feature_mgr.disconnect_db()

def update_db(database_file, dest_folder):
    
    # Create updater and connect
    updater = DBDatasetUpdater()
    updater.connect_db(database_file)

    # Apk main data updated
    rowcount = updater.update_db(dest_folder)
    print("%s downloaded rows successfully updated" % rowcount)
    
    updater.disconnect_db()

    # Create feature_mgr
    feature_mgr = FeatureManager()
    feature_mgr.connect_db(database_file)

    # Apk Features updated
    rowcount = feature_mgr.update_db(dest_folder)
    print("%s apk features updated" % rowcount)

    feature_mgr.disconnect_db()

if __name__ == '__main__':
    main()