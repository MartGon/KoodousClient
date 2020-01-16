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
            self.add_apk_db(apk_path, sha256=sha256, is_malware=is_malware) 
            
            print("Warning: APK %s not found in DB. Updating DB" % apk)
        else:
            self.dbclient.execute('''Update apks set downloaded = 1 WHERE sha256=:sha256''', query)

            # Save file if it does not exist
            self.dbclient.execute('''SELECT downloaded, filename FROM apks WHERE sha256=:sha256''',query)
            result = self.dbclient.fetchone()
            
            filename = result['filename']
            dest_folder = os.path.dirname(apk_path)

            # Remove if file can be found
            if os.path.exists(os.path.join(dest_folder, filename)):
                print("Warning: APK %s with a different name (%s) already found, deleting new one" % (apk, filename))
                os.remove(apk_path)
            # Set new file as filename if previous cannot be found
            else:
                query['filename'] = apk
                self.dbclient.execute('''Update apks set filename = :filename WHERE sha256=:sha256''', query)
            
        self.dbclient.commit()

        return sha256

    def add_apk_db(self, apk_path, sha256=None, is_malware = None):

        apk = APK(apk_path)
    
        # Insert into database
        data = {'sha256': sha256, 'filename': os.basename(apk_path), 'malware': is_malware, 'icon' : self.extract_apk_icon(apk_path), 'pkg_name': self.extract_apk_pkg_name()}
        self.dbclient.execute('''INSERT OR IGNORE INTO apks(sha256, filename, malware, icon, downloaded, package_name) VALUES(:sha256, :filename, :malware, :icon, 1, :pkg_name)''', data)  

    def extract_apk_pkg_name(self, apk_path, apk=None):

        # Androguard analyze if not provided already
        if apk is None:
            apk = APK(apk_path)

        return apk.self.apk.get_package()

    def extract_apk_icon(self, apk_path, apk=None):

        b64 = None

        # Androguard analyze if not provided already
        if apk is None:
            apk = APK(apk_path)

        # Extract icon filename
        icon_path = None
        try:
            icon_path = apk.get_app_icon()
        except ResParserError as e:
            pass

        if icon_path:
            # Extract icon to byte array
            zipi = zipfile.ZipFile(apk_path)

            try:
                zipi.extract(icon_path)
            except KeyError:
                pass

            icon_file = open(icon_path, 'rb')
            data = icon_file.read()
            icon_file.close()

            # Encode into b64 str
            b64 = base64.encodebytes(data)

        return b64

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
                 
        
    