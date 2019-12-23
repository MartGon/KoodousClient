from DatabaseMgr.DatabaseMgr import *

# Androguard
import androguard
import androguard.misc
import androguard.core.bytecodes.apk

# Androwarn
import androwarn
from warn.search.search import grab_application_package_name
from warn.util.util import *
from warn.analysis.analysis import perform_analysis_data

# AndroPyTool

from AndroPyTool.AndroPyAPI import *

# Certificates
import cryptography.x509
from cryptography.hazmat.backends import default_backend
import OpenSSL.crypto as crypto

# Scipy
from scipy.stats import *

# Filetype
import filetype

# Filge guessing
import mimetypes

import zipfile
import argparse
import math
import os

class APKCorruptedException(Exception):
    pass

class APKFeatures:

    apk_filename = None

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

    def get_misc_features(self):

        misc_features = {}
        misc_features['boolean_features'] = {}
        misc_features['continuous_features'] = {}

        # Cert Features
        misc_features['continuous_features']['cert_entropy'] = 0.0
        misc_features['continuous_features']['cert_name_length'] = 0.0
        try:
            sign_name = self.apk.get_signature_name()
            cert_data = self.apk.get_certificate(sign_name)
            cert = cryptography.x509.load_der_x509_certificate(cert_data.dump(), default_backend())
            alt_cert = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_data.dump())

            # Subject entropy
            cn = alt_cert.get_subject().CN
            if cn:
                binary_cn = ' '.join(format(ord(x), 'b') for x in cn)
                misc_features['continuous_features']['cert_entropy'] = round(calc_entropy(binary_cn), 4)
                misc_features['continuous_features']['cert_name_length'] = len(cn)

            # Check cert date against package date
            zipi = zipfile.ZipFile(self.apk_filename)
            pkg_date = zipi.getinfo("classes.dex").date_time
            cert_date = cert.not_valid_before

            misc_features['boolean_features']['cert_date'] = pkg_date[0] == cert_date.year and pkg_date[1] == cert_date.month
        except androguard.core.bytecodes.apk.FileNotPresent as e:
            print("Could not find certificate")

        # Package name features

        # Package name entropy
        pkg_name = self.apk.get_package()
        binary_pkgn = ' '.join(format(ord(x), 'b') for x in pkg_name)
        misc_features['continuous_features']['pkg_entropy'] = round(calc_entropy(binary_pkgn), 4)
        misc_features['continuous_features']['pkg_name_length'] = len(pkg_name)

        # Package prefix of every activity
        activities = self.apk.get_activities()

        count = 0
        for activity in activities:
            if activity.startswith(pkg_name):
                count = count + 1
        
        misc_features['boolean_features']['pgk_prefix'] = count <= len(activities) * 0.75

        # APK files features

        # TODO _ Improve, fails with zip vs apk and ico vs png
        misc_features['boolean_features']['incognito_app'] = False
        misc_features['boolean_features']['extension_mismatch'] = False

        misc_features['continuous_features']['files'] = len(self.apk.get_files())
        try:
            file_types = self.apk.get_files_types()
            for file in file_types:
                type = file_types[file]
                if type is not None:
                    type = '.' + type
                    mimetype,_ = mimetypes.guess_type(file)
                    if mimetype is not None:
                        guess = mimetypes.guess_all_extensions(mimetype, False)

                        # Check for incognito apk
                        if '.apk' in guess:
                            misc_features['boolean_features']['incognito_app'] = True

                        # Check for file extension mismtach
                        if type not in guess:
                            misc_features['boolean_features']['extension_mismatch'] = True
                            print('Mismatch found on file %s: Type %s vs Ext %s' % (file, type, guess))
                            break

        except (zipfile.BadZipFile, androguard.core.bytecodes.apk.FileNotPresent) as e:
            print("Bad crc32 found")

        # Other boolean features
        misc_features['boolean_features']['android_tv'] = self.apk.is_androidtv()
        misc_features['boolean_features']['lean_back'] = self.apk.is_leanback()
        misc_features['boolean_features']['multi_dex'] = self.apk.is_multidex()
        misc_features['boolean_features']['signed'] = self.apk.is_signed()
        misc_features['boolean_features']['is_wearable'] = self.apk.is_wearable()

        # Other continuous features
        misc_features['continuous_features']['activities'] = len(self.apk.get_activities())
        misc_features['continuous_features']['providers'] = len(self.apk.get_providers())
        misc_features['continuous_features']['receivers'] = len(self.apk.get_receivers())
        misc_features['continuous_features']['services'] = len(self.apk.get_services())

        misc_features['continuous_features']['permissions'] = len(self.apk.get_permissions())
        misc_features['continuous_features']['declared_permissions'] = len(self.apk.get_declared_permissions())
        misc_features['continuous_features']['third_party_permissions'] = len(self.apk.get_requested_third_party_permissions())

        misc_features['continuous_features']['sdk_version'] =  self.apk.get_effective_target_sdk_version()

        misc_features['continuous_features']['main_activity_name_length'] = len(self.apk.get_main_activity()) if self.apk.get_main_activity() is not None else 0

        return misc_features

    # TODO - Get commands, libs, file ext, file types
    # Config - Struct with commands, and apis to search for
    def get_static_features(self):

        andro_api = AndroPyAPI()

        return andro_api.get_static_features(self.apk_filename)

class FeatureExtractor:

    def extract_apk_features(self, apk_file):
        apk_features = APKFeatures()
        apk_features.apk_filename = apk_file
        apk_features.apk = androguard.core.bytecodes.apk.APK(apk_file)

        return apk_features

    def extract_features(self, apk):
        apk_features = APKFeatures()
        
        apk_features = apk
        try:
            apk_features.apk, apk_features.dvm, apk_features.analysis = androguard.misc.AnalyzeAPK(apk)
        except:
            print("%s was corrupted!" %apk)
            raise APKCorruptedException("APK was corrupted")

        # package_name = grab_application_package_name(apk_features.apk)
        apk_features.data = perform_analysis_data(apk, apk_features.apk, apk_features.dvm, apk_features.analysis, False)
        
        return apk_features

# Feature Updaters

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

    def get_apk_id(self, filename):
        # Get apk ID by filename
        self.dbclient.execute('''SELECT sha256 FROM apks WHERE filename = :filename''', {'filename' : filename})
        return self.dbclient.fetchone()[0]

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
    table_name = 'misc_features'
    column_name = 'misc_feature'

    API_PACKAGE_LIST_FILE = ''
    API_CLASSES_LIST_FILE = ''
    SYSTEM_COMMANDS_LIST_FILE = ''

    def extract_features(self, apk_file):
        return self.feature_extractor.extract_apk_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        # TODO _ Save features
        misc_features = apk_features.get_misc_features()

        # Boolean features
        boolean_features_dict = misc_features['boolean_features']
        boolean_features = [f for f in boolean_features_dict if boolean_features_dict[f]]
        self.save_features_values(apk_filename, boolean_features, self.table_name, self.relation_name, self.column_name)

        # continuous features
        args = misc_features['continuous_features']
        args['apk'] = self.get_apk_id(apk_filename)

        # Entropy
        self.dbclient.execute("INSERT OR IGNORE INTO apk_misc_continuous_features(apk, cert_entropy, pkg_entropy) VALUES(:apk, :cert_entropy, :pkg_entropy)", args)

        # Name lengths
        self.dbclient.execute("UPDATE OR IGNORE apk_misc_continuous_features SET cert_name_length = :cert_name_length, pkg_name_length = :pkg_name_length WHERE apk = :apk", args)

        # Componets
        self.dbclient.execute("UPDATE OR IGNORE apk_misc_continuous_features SET activities = :activities, services = :services, providers = :providers, receivers = :receivers WHERE apk = :apk", args)

        # Files
        self.dbclient.execute("UPDATE OR IGNORE apk_misc_continuous_features SET files = :files WHERE apk = :apk", args)

        # Permissions
        self.dbclient.execute("UPDATE OR IGNORE apk_misc_continuous_features SET permissions = :permissions, declared_permissions = :declared_permissions, third_party_permissions = :third_party_permissions WHERE apk = :apk", args)

        # Misc
        self.dbclient.execute("UPDATE OR IGNORE apk_misc_continuous_features SET sdk_version = :sdk_version, main_activity_name_length = :main_activity_name_length WHERE apk = :apk", args)

        self.dbclient.commit()

class StaticFeatureUpdater(FeatureUpdater):

    relation_name = 'apk_static_features'
    table_name = 'static_features'
    column_name = 'static_feature'

    def extract_features(self, apk_file):
        return self.feature_extractor.extract_apk_features(apk_file)

    def save_features(self, apk_features, apk_filename):
        apk_features.get_static_features(None)
        pass

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

FEATURE_UPDATER_LIST = {'p': PermissionUpdater(), 'f': FunctionalityUpdater(), 'm' : MiscFeatureUpdater(), 'l': LibraryUpdater(), 's': StaticFeatureUpdater()}

# Feature Managers

class FeatureManager(DatabaseManager):

    feature_updater_dict = FEATURE_UPDATER_LIST

    def __init__(self, feature):
        
        if feature in self.feature_updater_dict:
            self.feature_updater = self.feature_updater_dict[feature] 
        else:
            self.feature_updater = FullUpdater()

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

            sha256 = self.feature_updater.get_apk_id(apk)
            if self.feature_updater.should_update_apk(sha256):
                try:
                    print("Extracting features from %s" % apk)
                    apk_features = self.extract_features(apk_path)
                    self.save_features(apk_features, apk)
            
                except APKCorruptedException:
                    print("Removing from the system. Removing downloaded flag from database")
                    # os.remove(apk_path)
                    self.dbclient.execute('''UPDATE apks SET downloaded = 0 WHERE sha256 = :sha256''', {'sha256' : sha256})

            rowcount =  rowcount + 1
            print("%i/%i APKs updated" % (rowcount, len(apk_paths)))

        self.dbclient.commit()

def calc_entropy(input):

    e = 0
    if input is not None:
        if len(input) != 0:
            histogram = {}

            for char in input:
                if char in histogram:
                    histogram[char] = histogram[char] + 1
                else:
                    histogram[char] = 1

            n = len(histogram.keys())
            values = list(histogram.values())
            e = entropy(values, base = 2) / math.log2(n)

    return e