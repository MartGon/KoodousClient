from DatabaseMgr.DatabaseMgr import *

import play_scraper
import hashlib
import os
import requests
from bs4 import BeautifulSoup

class GooglePlayDownloader(DatabaseManager):

    def __init__(self, config_file):
        self.gplaycli_config = config_file
        self.headers ={'content-type': "application/json"}
        self.url = "http://127.0.0.1:3000/"
        pass
        
    def search(self, search_param, quantity=200):
        
        # Create body
        data = {"category": search_param, "num" : quantity}

        response = requests.post(url=self.url, headers=self.headers, json = data)
        results = response.json()

        print("Results found: " + str(len(results)))
        
        # Create apk dictionaries
        apks = []
        for i in range(0, len(results)):
            result = results[i]
            
            apk = {}
            apk['app_id'] = result['appId']
            apk['score'] = float(result['score']) if result['score'] is not None else 0
            apk['free'] = result['free']
            apk['filename'] = apk['app_id'] + ".apk"
            apks.append(apk)
            
            if len(apks) == quantity:
                break
                
        return apks
        
    def get_apk_details(self, appId):
        
        result = play_scraper.details(appId)
        
        return result
        
    def save_apk(self, apk):
        pass
        
    def download_apk(self, dest_folder, apk):
        
        if self.gplaycli_config is None:
            raise Exception("Google Play downloader config file is needed for downloads")

        # Get APK name
        filename = apk['app_id'] + ".apk"
        dest = os.path.join(dest_folder, filename)
        
        if os.path.exists(dest):
            print("Error: A file with same name already exists")
            return False
        
        # Download apk
        self.__gplaycli_download(apk['app_id'], dest_folder)
        
        if not os.path.exists(dest):
            print("Error: Download failed")
            return False

        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot download apk!")

        # Get Sha256
        file = open(dest, "rb")
        bytes = file.read()
        sha256 = hashlib.sha256(bytes).hexdigest()
        
        # Insert into database
        data = {'sha256': sha256, 'filename': filename, 'malware':False, 'package_name': apk['app_id'], 'downloaded' : True}
        self.dbclient.execute('''INSERT INTO apks(sha256, filename, malware, package_name, downloaded) VALUES(:sha256, :filename, :malware, :package_name, :downloaded)''', data)
        
        self.dbclient.commit()

        return True
        
    def update_db(dest_folder):
        pass
        
    def __gplaycli_download(self, appId, dest_folder):
        
        command = "gplaycli -d %s -f %s -c %s" % (appId, dest_folder, self.gplaycli_config)
        print(command)
        os.system(command)