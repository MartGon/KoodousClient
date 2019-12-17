from DatabaseMgr.DatabaseMgr import *

# Androguard
import androguard
import androguard.misc
import androguard.core.bytecodes.apk

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
            libraries = [library for library in analysis_results[category]]

        return libraries

    # TODO - Extract misc features
    def get_misc_features(self):
        pass


class FeatureExtractor:

    def extract_apk_features(self, apk_file):
        apk_features = APKFeatures()
        apk_features.apk = androguard.core.bytecodes.apk.APK(apk_file)

        return apk_features

    def extract_features(self, apk):
        apk_features = APKFeatures()

        try:
            apk_features.apk, apk_features.dvm, apk_features.analysis = androguard.misc.AnalyzeAPK(apk)
        except:
            print("%s was corrupted!" %apk)
            raise APKCorruptedException("APK was corrupted")

        # package_name = grab_application_package_name(apk_features.apk)
        apk_features.data = perform_analysis_data(apk, apk_features.apk, apk_features.dvm, apk_features.analysis, False)
        
        return apk_features

class FeatureUpdater(DatabaseManager):

    feature_extractor = FeatureExtractor()
    relation_name = None

    def save_features_values(self, apk_filename, values, table_name, relation_name, column_name):

        if values is not None:
            for value in values:
                query = {'value': value}
                self.dbclient.execute('''INSERT OR IGNORE INTO %s(info) VALUES(:value)''' % table_name, query)

                self.dbclient.execute('''SELECT id FROM %s WHERE info=:value''' % table_name, query)
                id = self.dbclient.fetchone()[0]
                self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename=:filename''', {'filename' : apk_filename})
                sha256 = self.dbclient.fetchone()[0]

                self.dbclient.execute('''INSERT OR REPLACE INTO %s(apk, %s) VALUES(:apk, :value)''' % (relation_name, column_name), {'apk' : sha256, 'value': id})

                self.dbclient.commit()

    def should_update_apk(self, apk):
        self.dbclient.execute('''SELECT count(*) from %s WHERE apk = :sha256''' % self.relation_name, {'sha256' : apk})
        count = self.dbclient.fetchone()[0]
        return count == 0

class PermissionUpdater(FeatureUpdater):

    relation_name = 'apk_permissions'

    def extract_features(self, apk_file):
        return self.feature_extractor.extract_apk_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update save features to DB!")
    
        # Get Permissions
        permissions = apk_features.get_permissions()
        self.save_features_values(apk_filename, permissions, 'permissions', self.relation_name, 'permission')

class FunctionalityUpdater(FeatureUpdater):

    relation_name = 'apk_functionalities'
    
    def extract_features(self, apk_file):
        return self.feature_extractor.extract_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update save features to DB!")

        # Get Functionalities
        functionalities = apk_features.get_functionalities()
        self.save_features_values(apk_filename, functionalities, 'functionalities', self.relation_name, 'functionality')

class LibraryUpdater(FeatureUpdater):
    
    relation_name = 'apk_libraries'

    def extract_features(self, apk_file):
        return self.feature_extractor.extract_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        # Check DB connection
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update save features to DB!")

        # Get Functionalities
        libraries = apk_features.get_loaded_libraries()
        self.save_features_values(apk_filename, libraries, 'libraries', 'apk_libraries', 'library')

class MiscFeatureUpdater(FeatureUpdater):

    relation_name = 'apk_misc_features'

    def extract_features(self, apk_file):
        return self.feature_extractor.extract_apk_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        pass

    def should_update_apk(self, apk):
        return False

class FullUpdater(FeatureUpdater):

    def extract_features(self, apk_file):
        return self.feature_extractor.extract_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        for feature_updater in list(FeatureManager.feature_updater_dict.values()):
            feature_updater.dbclient = self.dbclient

            feature_updater.save_features(apk_features, apk_filename)

    def should_update_apk(self, apk):
        for feature_updater in list(FeatureManager.feature_updater_dict.values()):
            feature_updater.dbclient = self.dbclient

            if feature_updater.should_update_apk(apk):
                return True

class FeatureManager(DatabaseManager):

    feature_updater_dict = {'p': PermissionUpdater(), 'f': FunctionalityUpdater(), 'm' : MiscFeatureUpdater(), 'l': LibraryUpdater()}

    def __init__(self, feature):
        
        if feature in self.feature_updater_dict:
            self.feature_updater = self.feature_updater_dict[feature] 
        else:
            self.feature_updater = FullUpdater()

    def get_apk_id(self, filename):
        # Get apk ID by filename
        self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename = :filename''', {'filename' : filename})
        return self.dbclient.fetchone()[0]

    def extract_features(self, apk):
        return self.feature_updater.extract_features(apk)
        
    def save_features(self, apk_features, apk_filename):
        self.feature_updater.save_features(apk_features, apk_filename)
                
    def update_db(self, dest_folder):
    
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot update db!")

        self.feature_updater.dbclient = self.dbclient
            
        apk_paths = [os.path.join(dest_folder, f) for f in os.listdir(dest_folder) if os.path.isfile(os.path.join(dest_folder, f))]
        
        rowcount = 0
        for apk_path in apk_paths:            
            apk = os.path.basename(apk_path)

            sha256 = self.get_apk_id(apk)
            if self.feature_updater.should_update_apk(sha256):
                try:
                    print("Extracting features from %s" % apk)
                    apk_features = self.extract_features(apk_path)
                    self.save_features(apk_features, apk)
            
                except APKCorruptedException:
                    print("Removing from the system. Removing downloaded flag from database")
                    os.remove(apk_path)
                    self.dbclient.execute('''UPDATE apks SET downloaded = 0 WHERE sha256 = :sha256''', {'sha256' : sha256})

            rowcount =  rowcount + 1
            print("%i/%i APKs updated" % (rowcount, len(apk_paths)))

        self.dbclient.commit()