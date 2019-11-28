from DatasetMgr.KoodousApiClient import *
from DatabaseMgr.DatabaseMgr import *

import os
import hashlib

class KoodousDatasetDownloader(DatabaseManager):
    
    def __init__(self, token):
        self.apiclient = KoodousApiClient(token)

    def search(self, search_param, quantity=50, is_malware=True):
        
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
            raise DBConnectionException("Not Connected to DB. Cannot search db!")    
            
        self.dbclient.execute(search_param, *args)
        return self.dbclient.fetchall()
        
    def save_apk(self, apk):
    
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot save apk!")
    
        self.dbclient.execute('''insert or replace into apks (package_name, filename, sha256, malware) values(:package_name, :filename, :sha256, :malware)''', apk)
        
        for tag in apk['tags']:
            self.dbclient.execute('''insert or ignore into tags (info) values(:tag)''', {'tag': tag})   
            self.dbclient.execute('''select id from tags where info = :tag''', {'tag' : tag})
            id = self.dbclient.fetchone()[0]
            self.dbclient.execute('''insert or replace into apk_tags(apk, tag) values(?,?)''', [apk['sha256'], id])
            
        self.dbclient.commit()
            
    def download_apk(self, dest_folder, apk):
    
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot download apk!")
    
        sha256 = apk['sha256']
        filename = apk['filename']
        result = False
        
        path = os.path.join(dest_folder, filename)
        if not os.path.exists(path):
        
            # Get failing servers
            self.dbclient.execute('''SELECT id FROM failing_servers''')
            server_ids = self.dbclient.fetchall()
            failing_servers = [str("lmcn" + str(id['id'])) for id in server_ids]
        
            result, download_url = self.apiclient.download(sha256, path, failing_servers)
            query = {'sha256' : sha256, 'download_url' : download_url}
            
            if result == 200:
                if os.path.exists(path):
                    print("Info: Download was succesful")
                    self.dbclient.execute('''Update apks SET downloaded = 1, download_url = :download_url where sha256=:sha256''', query)
                    self.dbclient.commit()
                    result = True
                else:
                    print("Error: Download of %s failed" % filename)
                    result = False
            elif result == 429:
                print("Error: Download failed. Max Daily download rate reached")
                result = False
            elif result == 430:
                print("Error: No more tokens left")  
                result = False
            elif result == 404:
                print("Error: Could not download from this server, updated download failed flag")
                self.dbclient.execute('''Update apks SET download_failed = 1, download_url = :download_url where sha256=:sha256''', query)
                self.dbclient.commit()
                result = False
        # File exists
        else:
            print("Warning: File with same name already exists. Download aborted")
            result = False
            
        return result
        
    def update_db(self, dest_folder, is_malware=True):
    
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")
            
        apks = [f for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk in apks:
        
            query = {'filename' : apk}
        
            # Check if apk exists in databese
            self.dbclient.execute('''SELECT count(*) FROM apks WHERE filename=:filename''', query)
            count = self.dbclient.fetchone()[0]
            
            # Apk doesn't exist in database -> Add it
            if count == 0:
                # Calculate sha256 digest of file
                apk_path = os.path.join(dest_folder, apk)
                file = open(apk_path, "rb")
                bytes = file.read()
                sha256 = hashlib.sha256(bytes).hexdigest()
                
                # Insert into database
                data = {'sha256': sha256, 'filename': apk, 'malware':is_malware}
                self.dbclient.execute('''INSERT INTO apks(sha256, filename, malware) VALUES(:sha256, :filename, :malware''', data)     
                
                print("Warning: APK %s not found in DB. Updating DB" % apk)
            else:
            
                # Check if apk has been downloaded
                self.dbclient.execute('''SELECT downloaded FROM apks WHERE filename=:filename''',query)
                downloaded = self.dbclient.fetchone()[0]
                
                if not downloaded:
                    self.dbclient.execute('''Update apks set downloaded = 1 where filename=:filename''', query)
                    rowcount =  rowcount + 1
            
        self.dbclient.commit()
        
        return rowcount