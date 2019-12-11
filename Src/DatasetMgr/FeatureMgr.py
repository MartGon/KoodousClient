from DatabaseMgr.DatabaseMgr import *

# Androguard
import androguard
import androguard.misc

# Androwarn
import androwarn
from warn.search.search import grab_application_package_name
from warn.analysis.analysis import perform_analysis_data

import argparse
import os

class APKCorruptedException(Exception):
    pass

class APKFeatures:

    # Androguard
    apk = None
    dvm = None
    analysis = None

    # Androwarn
    data = None

    def __init__(self):
        pass
        
    def get_permissions(self):
        return self.apk.get_permissions()

    def get_functionalities(self):

        functionalities = []
        analysis_categories = (['telephony_identifiers_leakage', 'device_settings_harvesting', 'location_lookup', 
                                'connection_interfaces_exfiltration', 'telephony_services_abuse', 'audio_video_eavesdropping',
                                'suspicious_connection_establishment', 'PIM_data_leakage', 'code_execution'])

        analysis_results = self.data[1]['analysis_results']
        for category in analysis_categories:
            if category in analysis_results:
                for functions in analysis_results[category]:
                    functionalities.append(functions)
        
        return functionalities

    def get_loaded_libraries(self):

        libraries = []

        analysis_results = self.data[1]['analysis_results']
        category = 'loaded_libraries'

        if category in analysis_results:
            libraries = [library for liibrary in analysis_results[category]]

        return libraries


class FeatureExtractor:

    def extract_features(self, apk):
        apk_features = APKFeatures()
        try:
            apk_features.apk, apk_features.dvm, apk_features.analysis = androguard.misc.AnalyzeAPK(apk)
        except:
            print("%s was corrupted!" %apk)
            raise APKCorruptedException("APK was corrupted")

        package_name = grab_application_package_name(apk_features.apk)
        apk_features.data = perform_analysis_data(apk, apk_features.apk, apk_features.dvm, apk_features.analysis, False)
        
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
        self.get_relation_values(apk_filename, permissions, 'permissions', 'apk_permissions', 'permission')

        # Get Functionalities
        functionalities = apk_features.get_functionalities()
        self.get_relation_values(apk_filename, functionalities, 'functionalities', 'apk_functionalities', 'functionality')

        # Get Libraries
        libraries = apk_features.get_loaded_libraries()
        self.get_relation_values(apk_filename, libraries, 'libraries', 'apk_libraries', 'library')


    def get_relation_values(self, apk_filename, values, table_name, relation_name, column_name):

        for value in values:
            query = {'value': value}
            self.dbclient.execute('''INSERT OR IGNORE INTO %s(info) VALUES(:value)''' % table_name, query)

            self.dbclient.execute('''SELECT id FROM %s WHERE info=:value''' % table_name, query)
            id = self.dbclient.fetchone()[0]
            self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename=:filename''', {'filename' : apk_filename})
            sha256 = self.dbclient.fetchone()[0]

            self.dbclient.execute('''INSERT OR REPLACE INTO %s(apk, %s) VALUES(:apk, :value)''' % (relation_name, column_name), {'apk' : sha256, 'value': id})

            self.dbclient.commit()

            print(value)
            
    def update_db(self, dest_folder):
    
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")
            
        apk_paths = [os.path.join(dest_folder, f) for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk_path in apk_paths:
            
            apk = os.path.basename(apk_path)
            self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename = :filename''', {'filename' : apk})
            sha256 = self.dbclient.fetchone()[0]
            self.dbclient.execute('''SELECT count(*) from apk_functionalities WHERE apk = :sha256''', {'sha256' : sha256})
            count = self.dbclient.fetchone()[0]
            
            if count == 0:
                try:
                    apk_features = self.extract_features(apk_path)
                    self.save_features(apk_features, apk)
            
                    rowcount =  rowcount + self.dbclient.cursor.rowcount
                except APKCorruptedException:
                    print("Removing from the system. Removing downloaded flag from database")
                    os.remove(apk_path)
                    self.dbclient.execute('''UPDATE apks SET downloaded = 0 WHERE sha256 = :sha256''', {'sha256' : sha256})

        self.dbclient.commit()