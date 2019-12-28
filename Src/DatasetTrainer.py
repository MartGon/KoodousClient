from DatabaseMgr.DatabaseMgr import *

from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import GaussianNB
from sklearn.naive_bayes import BernoulliNB

from sklearn.model_selection import KFold

from sklearn.metrics.classification import accuracy_score
from sklearn.metrics.classification import f1_score

from random import shuffle
from joblib import dump, load

import argparse

class MalwareClassificator(DatabaseManager):
    
    # SQL Data
    column_name = None
    table_name = None
    relation_name = None
    continuous_relation_name = None
    counted_relation_name = None

    # Model
    model = None

    # Params
    n_features = 50

    # Caches
    relevant_features = []

    def __init__(self):
        pass

    def get_samples(self, dataset):

        # Get samples alongside its features in dictionary format
        samples = []
        for apk in dataset:
            sample = {}

            # Get main data
            sample['sha256'] = apk['sha256'] 
            sample['malware'] = apk['malware']

            # Get APK features
            sample['boolean-features'] = self.get_apk_boolean_features(apk['sha256'])
            sample['counted-features'] = self.get_apk_counted_features(apk['sha256'])
            sample['continuous-features'] = self.get_apk_continuous_features(apk['sha256'])

            samples.append(sample)

        shuffle(samples)

        return samples

    def fit(self, samples):
        
        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        training_data, training_labels = self.construct_data(samples, relevant_features)

        # Fit model
        self.model.fit(training_data, training_labels)

    def predict(self, samples):

        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        data, labels = self.construct_data(samples, relevant_features)

        return labels, self.model.predict(data)

    # Performance Eval
    def get_training_results(self, database_file, dataset, cross_validation = 10):
        
        # Connect to DB
        self.connect_db(database_file)

        # Get samples
        samples = self.get_samples(dataset)

        results = []
        # K-Fold Cross Validation
        kf = KFold(n_splits=cross_validation)
        for train, test in kf.split(samples):

            # Get training and testing samples from index
            training_samples = [samples[i] for i in train]
            testing_samples = [samples[i] for i in test]

            # Fit model
            self.fit(training_samples)

            # Predict labels for testing samples
            testing_labels, predicted_labels = self.predict(testing_samples)

            # Get score
            result = {}
            result['accuracy'] = accuracy_score(testing_labels, predicted_labels, True)
            result['f-score'] = f1_score(testing_labels, predicted_labels)

            results.append(result)

        # Close DB Connection
        self.disconnect_db()
        
        return results

    # Feature methods

    def get_apk_boolean_features(self, apk):

        column_name = self.get_column()
        relation_name = self.get_relation()

        bool_features = []
        if relation_name:
            query = {'sha256' : apk, 'column' : column_name, 'relation' : relation_name}
            query_result = self.search_db('''select %s from %s where apk = :sha256''' % (column_name, relation_name), query)
            bool_features = [f[column_name] for f in query_result]

        return bool_features

    def get_apk_counted_features(self, apk):

        column_name = self.get_column()
        relation_name = self.get_counted_relation()

        results = {}
        if relation_name:
            query = {'sha256' : apk, 'column' : column_name, 'relation' : relation_name}
            query_result = self.search_db('''select %s, count from %s where apk = :sha256''' % (column_name, relation_name), query)

            for row in query_result:
                results[row[column_name]] = row['count']

        return results

    def get_apk_continuous_features(self, apk):

        relation_name = self.get_continuous_relation()

        continuous_features = []
        if relation_name is not None:

            query = {'sha256': apk}
            query_result = self.search_db('''SELECT * FROM %s where apk = :sha256''' % relation_name, query)

            continuous_features = []
            if len(query_result) == 1:
                row = query_result[0]
                row_data = [row[column] for column in row.keys()]

                # Removing apk column
                continuous_features = row_data[1:]

        return continuous_features
    
    def get_relevant_features(self):
        
        if len(self.relevant_features) == 0:
        
            column_name = self.get_column()
            relation_name = self.get_relevant_relation()

            if relation_name:
                query = {'n_features' : self.n_features}
                query_result = self.search_db('''select %s, count(*) from %s GROUP BY %s ORDER BY count(*) DESC LIMIT :n_features''' % (column_name, relation_name, column_name), query)
                self.relevant_features = [f[column_name] for f in query_result]

        return self.relevant_features

    # Util

    def construct_data(self, training_samples, relevant_features):

        data = []
        labels = []
        for apk in training_samples:        
            features = []

            # Boolean features
            if apk['boolean-features'] is not None:
                for feature in relevant_features:
                    if feature in apk['boolean-features']:
                        features.append(1)
                    else:
                        features.append(0)

            # Counted features
            if apk['counted-features'] is not None:
                for feature in relevant_features:
                    if feature in apk['counted-features']:
                        features.append(apk['counted-features'][feature])
                    else:
                        features.append(0)

            # Continuous features
            if apk['continuous-features'] is not None:
                for feature in apk['continuous-features']:
                    features.append(feature)

            data.append(features)
            if 'malware' in apk:
                labels.append(apk['malware'])

        return data, labels

    # DB Management

    def get_column(self):
        return self.column_name
    
    def get_table(self):
        return self.table_name

    def get_relation(self):
        return self.relation_name
    
    def get_continuous_relation(self):
        return self.continuous_relation_name

    def get_counted_relation(self):
        return self.counted_relation_name

    def get_relevant_relation(self):
        return self.get_relation()

    def get_model(self):
        return self.model

    # Serialization
    def dump_model(self, model_output_file):
    
        if model_output_file:
            dump(self.model, model_output_file)

# Q = 20
class PermissionMalwareClassificator(MalwareClassificator):

    column_name = 'permission'
    table_name = 'permissions'
    relation_name = 'apk_permissions'
    model = BernoulliNB()

# Q = 57 (max)
class FunctionalitiesMalwareClassificator(MalwareClassificator):

    column_name = 'functionality'
    table_name = 'funtionalities'
    relation_name = 'apk_functionalities'
    model = MultinomialNB()

# Q = 8 (max)
class MiscFeatureMalwareClassificator(MalwareClassificator):

    column_name = 'misc_feature'
    table_name = 'misc_features'
    relation_name = 'apk_misc_features'
    continuous_relation_name = 'apk_misc_continuous_features'
    model = GaussianNB()

    def get_apk_continuous_features(self, apk):
        continuous_features = super().get_apk_continuous_features(apk)

        if len(continuous_features) == 0:
            res = self.search_db('''SELECT * FROM apk_misc_continuous_features''')[0]
            length = len(res.keys())

            continuous_features = [0 for f in range(1, length)]
        return continuous_features

# Q = 500 (Can be increased, takes much more time)
class StaticFeatureMalwareClassificator(MalwareClassificator):

    column_name = 'static_feature'
    table_name = 'static_features'
    counted_relation_name = 'apk_static_features'
    model = GaussianNB()

    def get_relevant_relation(self):
        return self.counted_relation_name

class EnsembledMalwareClassificator(MalwareClassificator):

    classifiers = None

    def __init__(self, classifiers):
        self.classifiers = classifiers

    def fit(self, s):
        pass
    

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--feature-key', '-fk', help = 'Features that will be used for training can be (p, f)', required=True)
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--quantity', '-q', help = 'Number of top used features to employ', required=False, default=5, type=int)
    argparser.add_argument('--cross-validation', '-cv', help='Cross Validation iterations', required=False, default=10, type=int)
    argparser.add_argument('--csv-output-file', '-csv', help='CSV output file for results', required=False)
    argparser.add_argument('--model-output-file', '-mof', help='Model output file location for dumping', required=False)

    # Parse arguments
    args = argparser.parse_args()
    database_file = args.database_file
    n_permissions = args.quantity
    feature_key = args.feature_key

    # Create classifier
    classifier = None
    if feature_key == 'p':
        classifier = PermissionMalwareClassificator()
    elif feature_key == 'f':
        classifier = FunctionalitiesMalwareClassificator()
    elif feature_key == 'm':
        classifier = MiscFeatureMalwareClassificator()
    elif feature_key == 's':
        classifier = StaticFeatureMalwareClassificator()
    else:
        argparser.error("Unrecognized classificator identifier")

    # Set params
    classifier.n_features = n_permissions

    # TODO - Get APK list to use as dataset
    dbclient = SQL3Client()
    dbclient.connect(database_file)
    dbclient.execute('''SELECT * FROM apks WHERE downloaded = 1''')
    dataset = dbclient.fetchall()
    dbclient.close()

    # Get training results
    results = classifier.get_training_results(database_file, dataset, args.cross_validation)

    # Get Measures
    accuracy_avg = round(sum([f['accuracy'] for f in results]) / len(results) * 100, 2)
    f_score_avg = round(sum([f['f-score'] for f in results]) / len(results) * 100, 2)

    print()
    print("Info: Accuracy = %f" % accuracy_avg)
    print("Info: F-Score = %f" % f_score_avg)

    # Write csv results
    write_results(results, args.csv_output_file, accuracy_avg, f_score_avg)

    # Dump model
    classifier.dump_model(args.model_output_file)

def write_results(results, file_location, accuracy_avg, f_score_avg):

    if file_location is not None:

        # Open file
        file = open(file_location, "w")

        # Write header
        file.write("KFold, Accuracy, F-score \n")

        for i in range(0, len(results)):
            result = results[i]

            # Generate row
            tag = "C%i" % (i + 1)
            row = "%s, %f, %f \n" %(tag, result['accuracy'], result['f-score'])
        
            file.write(row)
    
        # Write avg
        row = "Total, %f, %f \n" %(accuracy_avg, f_score_avg)

        file.write(row)

        file.close()

if __name__ == '__main__':
    main()