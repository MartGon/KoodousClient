from DatabaseMgr.DatabaseMgr import *

import play_scraper
import hashlib
import os
import requests
from bs4 import BeautifulSoup

class GooglePlayDownloader(DatabaseManager):

    def __init__(self, config_file):
        self.gplaycli_config = config_file
        pass
        
    def search(self, search_param, quantity=50):
        
        apks = []
        page = 0
        while len(apks) < quantity:
            results = play_scraper.search(query=search_param, page=page, detailed=True)
            print("Results found: " + str(len(results)))
            
            # Create apk dictionaries
            for i in range(0, min(quantity, len(results))):
                result = results[i]
                
                apk = {}
                apk['app_id'] = result['app_id']
                apk['score'] = float(result['score']) if result['score'] is not None else 0
                apk['reviews']= result['reviews']
                apk['free'] = result['free']
                apk['filename'] = result['app_id'] + ".apk"
                
                apks.append(apk)
                
            page = page + 1
                
        return apks
        
    def get_apk_details(self, appId):
        
        result = play_scraper.details(appId=appId)
        #print(result)
        
        return result
        
    def save_apk(self, apk):
        pass
        
    def download_apk(self, dest_folder, apk):
        
        # Get APK name
        filename = apk['app_id'] + ".apk"
        dest = os.path.join(dest_folder, filename)
        
        if os.path.exists(dest):
            print("Error: A file with same name already exists")
            return
        
        # Download apk
        self.__gplaycli_download(apk['app_id'], dest_folder)
        
        if not os.path.exists(dest):
            print("Error: Download failed")
            return

        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot download apk!")

        # Get Sha256
        file = open(dest, "rb")
        bytes = file.read()
        sha256 = hashlib.sha256(bytes).hexdigest()
        
        # Insert into database
        data = {'sha256': sha256, 'filename': filename, 'malware':False, 'package_name': apk['app_id']}
        self.dbclient.execute('''INSERT INTO apks(sha256, filename, malware, package_name) VALUES(:sha256, :filename, :malware, :package_name)''', data)
        
        self.dbclient.commit()
        
    def update_db(dest_folder):
        pass
        
    def __gplaycli_download(self, appId, dest_folder):
        
        command = "gplaycli -d %s -f %s -c %s" % (appId, dest_folder, self.gplaycli_config)
        print(command)
        os.system(command)