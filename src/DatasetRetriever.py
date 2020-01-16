from DatasetMgr.KoodousDownloader import *
from DatasetMgr.FeatureMgr import *
from DatasetMgr.GoodwareDownloader import *
from DatasetMgr.DBDatasetUpdater import *

import argparse
import sqlite3
import os
import math

MAX_DOWNLOAD_PER_DAY = 50
SQL_DB_CONFIG_FILE = "dbconfig.sql"
        
def main():
    
    # Config arg parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--tokens', '-t', help = 'Koodous API Token', required=False, nargs='+')
    argparser.add_argument('--search', '-s', help = 'Koodous search string', required=False)
    argparser.add_argument('--download', '-d', help = 'Whether to download samples', required=False, default=False)
    argparser.add_argument('--quantity', '-q', help = 'Amount of apps to search/download', required=False, type=int) 
    argparser.add_argument('--is-malware', '-iw', help = 'Whether to consider the result apks as malware', required=False, type=int, default=1)
    
    database = argparser.add_argument_group('database')
    database.add_argument('--database-file', '-dbf', help = 'SQLite3 database file location', required=False)
    database.add_argument('--feature-update', '-fu', help = 'Update provided database file with already downloaded apks and using select feature', required = False, default=None)
    
    download = argparser.add_argument_group('download')
    download.add_argument('--dest-folder', '-df', help = 'Download destination folder', required=False)
    download.add_argument('--gplaycli-conf', '-gp', help = 'GooglePlayCLI config file', required=False)


    # Parse arguments
    args = argparser.parse_args()
    
    # Get data
        # Mandatory
    tokens = args.tokens if args.tokens is not None else ["null"]
    search_param = args.search
    do_download = args.download
    
        # Optional
    quantity = args.quantity if args.quantity is not None else 50
    is_malware = args.is_malware
    database_file = os.path.abspath(args.database_file) if args.database_file else None
    dest_folder = os.path.abspath(args.dest_folder) if args.dest_folder else None
    feature_update = args.feature_update
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

        # Print results
        else:
            for apk in apks:
                print(apk)

    # No Search, Download and Database         
    else:
        
        # Download request
        if dest_folder:        
            
            if database_file:
                    
                # Get apks marked for download in DB                
                if do_download:

                    # Download only malware
                    if is_malware:  
                        # Create Api client by goodware or malware
                        downloader = KoodousDatasetDownloader(tokens)
                        
                        # Connect to DB
                        downloader.connect_db(database_file)

                        # Search for download canditates
                        results = downloader.search_db('''Select sha256, filename from apks where downloaded=0 AND download_failed=0''')
                        print("Found %i download candidates" % len(results))

                        # Disconnect from DB
                        downloader.disconnect_db()

                        # Download apks
                        download_apks(downloader = downloader, tokens = tokens, database_file = database_file, apks = results, dest_folder = dest_folder)
                    
                    # Goodware
                    else:

                        # Create Api client by goodware or malware
                        downloader = GooglePlayDownloader(gplaycli_conf)

                        # Connect to DB
                        downloader.connect_db(database_file)

                        # How many should be downloaded
                        results = downloader.search_db('''Select sha256 from apks where downloaded = 1 AND malware = 1''')
                        malware_donwloaded = len(results)
                        results = downloader.search_db('''Select sha256,package_name from apks where downloaded = 1 AND malware = 0''')
                        downloaded_goodware_packages = [f['package_name'] for f in results]
                        to_download = malware_donwloaded - len(downloaded_goodware_packages)

                        print("Info:%s goodware apks to download" % to_download)

                        # Get apks to download
                        categories = [f for f in play_scraper.categories()]

                        # Download apks
                        downloaded_apks = []
                        category_index = 0
                        while len(downloaded_apks) < to_download:
                            category = categories[category_index % len(categories)]

                            found_apks = downloader.search(category)
                            print("Info: Found %s suitable apps from category %s" % (len(found_apks), category))

                            candidates = [f for f in found_apks if f['app_id'] not in downloaded_goodware_packages and f['score'] >= 4.0]
                            for apk in candidates:
                                if downloader.get_apk_details(apk['app_id'])['reviews'] > 10000:
                                    print("Info: Trying to download %s" % apk['app_id'])
                                    if downloader.download_apk(dest_folder, apk):
                                        print("Info: %s was downloaded successfully" % apk['app_id'])
                                        downloaded_apks.append(apk)

                                        print("Info: %i/%i apks downloaded so fat" % (len(downloaded_apks), to_download))
                                        break
                            
                            category_index = category_index + 1

                        # Disconnect from DB
                        downloader.disconnect_db()
                
                # Check if database should be updated
                if feature_update is not None:
                    update_db(database_file, dest_folder, feature_update)

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
    for apk in apks:
        print("Trying to download %s" % apk['filename'])
            
        try:
            if downloader.download_apk(dest_folder, apk):
            
                # Increase download count
                download_amount = download_amount + 1
                
        except DownloadException:
            print("Exception: DownloadException caught")
            break
            
    print("%i Apps Downloaded" % download_amount)

    # Disconnect from DB
    downloader.disconnect_db()

def update_db(database_file, dest_folder, feature_update):
    
    # Create updater and connect
    updater = DBDatasetUpdater()
    updater.connect_db(database_file)

    # Apk main data updated
    rowcount = updater.update_db(dest_folder)
    print("%s downloaded rows successfully updated" % rowcount)
    
    updater.disconnect_db()

    # Create feature_mgr
    feature_mgr = FeatureManager(feature_update)
    feature_mgr.connect_db(database_file)

    # Apk Features updated
    rowcount = feature_mgr.update_db(dest_folder)
    print("%s apk features updated" % rowcount)

    feature_mgr.disconnect_db()

if __name__ == '__main__':
    main()