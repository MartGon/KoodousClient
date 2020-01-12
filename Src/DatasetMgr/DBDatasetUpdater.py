from DatabaseMgr.DatabaseMgr import *

import os
import hashlib

class DBDatasetUpdater(DatabaseManager):

    def __init__(self):
        pass

    def update_db_apk(self, apk, dest_folder=""):

        # Check DB Connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")

        # Calculate apk hash
        apk_path = os.path.join(dest_folder, apk)
        sha256 = self.sha256(apk_path)

        query = {'sha256' : sha256}
    
        # Check if apk exists in databese
        self.dbclient.execute('''SELECT count(*) FROM apks WHERE sha256=:sha256''', query)
        count = self.dbclient.fetchone()[0]
        
        # Apk doesn't exist in database -> Add it
        if count == 0:
            # Insert into database
            data = {'sha256': sha256, 'filename': apk, 'malware': self.is_malware(apk)}
            self.dbclient.execute('''INSERT OR IGNORE INTO apks(sha256, filename, malware) VALUES(:sha256, :filename, :malware)''', data)     
            
            print("Warning: APK %s not found in DB. Updating DB" % apk)
        else:
            # Check if apk has been downloaded
            self.dbclient.execute('''SELECT downloaded FROM apks WHERE sha256=:sha256''',query)
            downloaded = self.dbclient.fetchone()[0]
            
            if not downloaded:
                self.dbclient.execute('''Update apks set downloaded = 1 where WHERE sha256=:sha256''', query)
            
        self.dbclient.commit()

        return count == 0

    def update_db(self, dest_folder):
                # Check DB Connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")
            
        apks = [f for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk in apks:
            if self.update_db_apk(apk, dest_folder=dest_folder):
                rowcount = rowcount + 1
            
        self.dbclient.commit()

        return rowcount

    def sha256(self, apk):
        file = open(apk, "rb")
        bytes = file.read()
        return hashlib.sha256(bytes).hexdigest()

    def is_malware(self, filename):
        return filename.count('.') < 2
                 
        
    