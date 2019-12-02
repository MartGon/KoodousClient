from DatabaseMgr.DatabaseMgr import *

# Androguard
import androguard
import androguard.misc

import argparse
import os

class APKCorruptedException(Exception):
    pass

class APKFeatures:

    apk = None
    dvm = None
    analysis = None

    def __init__(self):
        pass
        
    def get_permissions(self):
        return self.apk.get_permissions()

class FeatureExtractor:

    def extract_features(self, apk):
        apk_features = APKFeatures()
        try:
            apk_features.apk, apk_features.dvm, apk_features.analysis = androguard.misc.AnalyzeAPK(apk)
        except:
            print("%s was corrupted!" %apk)
            raise APKCorruptedException("APK was corrupted")
        
        return apk_features
        
class FeatureManager(DatabaseManager):

    def __init__(self):
        self.feature_extractor = FeatureExtractor()

    def extract_features(self, apk):
        return self.feature_extractor.extract_features(apk)
        
    def save_features(self, apk_features, apk_filename):
        
        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update save features to DB!")
    
        # Get Permissions
        permissions = apk_features.get_permissions()
    
        print()
        print("%s Permissions:" % apk_filename) 
        for permission in permissions:
                                
            # Add permisison to DB
            query = {'permission' :permission}
            self.dbclient.execute('''INSERT OR IGNORE INTO permissions(info) VALUES(:permission)''', query)
            
            # Get apk and permisison IDs
            self.dbclient.execute('''SELECT id FROM permissions WHERE info=:permission''', query)
            id = self.dbclient.fetchone()[0]
            self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename=:filename''', {'filename' : apk_filename})
            sha256 = self.dbclient.fetchone()[0]
            
            # Add apk->permssion relation
            self.dbclient.execute('''INSERT OR REPLACE INTO apk_permissions(apk, permission) VALUES(:apk, :permission)''', {'apk' : sha256, 'permission' : id})
            
            # Committin changes
            self.dbclient.commit()
        
            print(permission)
            
    def update_db(self, dest_folder):
    
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")
            
        apk_paths = [os.path.join(dest_folder, f) for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk_path in apk_paths:
            
            apk = os.path.basename(apk_path)
            self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename = :filename''', {'filename' : apk})
            sha256 = self.dbclient.fetchone()[0]
            self.dbclient.execute('''SELECT count(*) from apk_permissions WHERE apk = :sha256''', {'sha256' : sha256})
            count = self.dbclient.fetchone()[0]
            
            if count == 0:
                try:
                    apk_features = self.extract_features(apk_path)
                    self.save_features(apk_features, apk)
            
                    rowcount =  rowcount + self.dbclient.cursor.rowcount
                except APKCorruptedException:
                    pass

        self.dbclient.commit()