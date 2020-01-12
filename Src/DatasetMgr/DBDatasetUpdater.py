from DatabaseMgr.DatabaseMgr import *

import os
import hashlib

class DBDatasetUpdater(DatabaseManager):

    def __init__(self):
        pass

    def update_db_apk(self, apk_path, is_malware=None):

        # Check DB Connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")

        # Calculate apk hash
        sha256 = self.sha256(apk_path)
        apk = os.path.basename(apk_path)

        query = {'sha256' : sha256}
    
        # Check if apk exists in databese
        self.dbclient.execute('''SELECT count(*) FROM apks WHERE sha256=:sha256''', query)
        count = self.dbclient.fetchone()[0]
        
        # Apk doesn't exist in database -> Add it
        if count == 0:
            # Insert into database
            data = {'sha256': sha256, 'filename': apk, 'malware': is_malware}
            self.dbclient.execute('''INSERT OR IGNORE INTO apks(sha256, filename, malware) VALUES(:sha256, :filename, :malware)''', data)     
            
            print("Warning: APK %s not found in DB. Updating DB" % apk)
        else:
            # Check if apk has been downloaded
            self.dbclient.execute('''SELECT downloaded, filename FROM apks WHERE sha256=:sha256''',query)
            result = self.dbclient.fetchone()
            downloaded = result['downloaded']
            
            if not downloaded:
                self.dbclient.execute('''Update apks set downloaded = 1 WHERE sha256=:sha256''', query)
            
            filename = result['filename']
            if apk != filename:
                print("Warning: APK %s with a different name (%s) already found, deleting new one" % (apk, filename))
                os.remove(apk_path)
            
        self.dbclient.commit()

        return sha256

    def update_db(self, dest_folder):
                # Check DB Connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")
            
        apks = [f for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk in apks:
            apk_path = os.path.join(apk, dest_folder)
            self.update_db_apk(apk, self.is_malware(apk))
            rowcount = rowcount + 1
            print("\rUpdated %i/%i APKS" % (rowcount, len(apks)), end='')
            
        self.dbclient.commit()

        return rowcount

    def sha256(self, apk):
        file = open(apk, "rb")
        bytes = file.read()
        return hashlib.sha256(bytes).hexdigest()

    def is_malware(self, filename):
        return filename.count('.') < 2
                 
        
    