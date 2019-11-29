from DatabaseMgr.DatabaseMgr import *

import os
import hashlib

class DBDatasetUpdater(DatabaseManager):

    def __init__(self):
        pass

    def update_db(self, dest_folder):
                # Check DB Connection
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
                data = {'sha256': sha256, 'filename': apk, 'malware': self.is_malware(apk)}
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

        def is_malware(self, filename):
            return filename.count('.') < 2
                 
        
        return rowcount