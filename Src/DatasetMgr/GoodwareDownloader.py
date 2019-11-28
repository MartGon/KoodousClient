from DatabaseMgr.DatabaseMgr import *

import play_scraper
import hashlib
import os

class GooglePlayDownloader(DatabaseManager):

    def __init__(self):
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
                
                print(apk)
                
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
        
        # Get download url
        url = self.__get_download_url(appId)
        
        # Download apk
        file = open(dest, "wb")
        response = requests.get(url)
        file.write(response.content)
        
        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot download apk!")
            
        # Get Sha256
        sha256 = hashlib.sha256(response.content).hexdigest()
        
        # Insert into database
        data = {'sha256': sha256, 'filename': filename, 'malware':False}
        self.dbclient.execute('''INSERT INTO apks(sha256, filename, malware) VALUES(:sha256, :filename, :malware''', data)
        
        self.dbclient.commit()
        
    def update_db(dest_folder):
        pass
        
    def __get_download_url(self, appId):
    
        response = requests.get('http://apk-dl.com/' + appId)
        soup = BeautifulSoup(response.content, 'html.parser')
        temp_link = soup.find("div",{'class': 'download-btn'}).find("a")["href"]

        response = requests.get('http://apk-dl.com/' + temp_link)
        soup = BeautifulSoup(response.content, 'html.parser')
        temp_link2 = soup.find("section",{'class': 'detail'}).find("a")["href"]

        response = requests.get(temp_link2)
        soup = BeautifulSoup(response.content, 'html.parser')
        temp_link3 = soup.find("div",{'class': 'contents'}).find("a")["href"]

        return "http:" + temp_link3