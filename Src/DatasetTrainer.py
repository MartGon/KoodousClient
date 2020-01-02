from DatabaseMgr.DatabaseMgr import *

from sklearn.base import BaseEstimator
from sklearn.base import ClassifierMixin
from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import GaussianNB
from sklearn.naive_bayes import BernoulliNB

from sklearn.model_selection import KFold

from sklearn.metrics.classification import accuracy_score
from sklearn.metrics.classification import f1_score

from random import shuffle
from joblib import dump, load

import argparse
import numpy as np

import concurrent.futures

class APKDatabase(DatabaseManager):

    apks = {}
    relevant_features = {}

    def get_apk_data(self, sha256, table_data):

        sample = {}

        if sha256 not in self.apks:
            # Get main data
            sample['sha256'] = sha256
            sample['malware'] = self.get_apk_type(sha256)

            # Get APK features
            sample[table_data['feature-group']] = self.get_group_features(sha256, table_data)

            # Insert
            self.apks[sha256] = sample
        else:
            # Get reference
            sample = self.apks[sha256]

            if table_data['feature-group'] not in sample:
                sample[table_data['feature-group']] = self.get_group_features(sha256, table_data)

        return sample

    def get_group_features(self, sha256, table_data):

        feature_group = {}
        feature_group['boolean-features'] = self.get_apk_boolean_features(sha256, table_data)
        feature_group['counted-features'] = self.get_apk_counted_features(sha256, table_data)
        feature_group['continuous-features'] = self.get_apk_continuous_features(sha256, table_data)

        return feature_group

    def get_apk_type(self, apk):

        query = {'apk': apk}
        result = self.search_db('''SELECT malware FROM apks where sha256=:apk''', query)

        if len(result) != 1:
            raise Exception("Inconsistent DB query")
        
        row = result[0]
        return row['malware'] == 1

    def get_apk_boolean_features(self, apk, table_data):

        column_name = table_data['column']
        relation_name = table_data['relation']

        bool_features = []
        if relation_name:
            query = {'sha256' : apk, 'column' : column_name, 'relation' : relation_name}
            query_result = self.search_db('''select %s from %s where apk = :sha256''' % (column_name, relation_name), query)
            bool_features = [f[column_name] for f in query_result]

        return bool_features

    def get_apk_continuous_features(self, apk, table_data):

        relation_name = table_data['continuous-relation']

        continuous_features = []
        if relation_name:

            query = {'sha256': apk}
            query_result = self.search_db('''SELECT * FROM %s where apk = :sha256''' % relation_name, query)

            continuous_features = []
            if len(query_result) == 1:
                row = query_result[0]
                row_data = [row[column] for column in row.keys()]

                # Removing apk column
                continuous_features = row_data[1:]
            elif len(query_result) == 0:
                res = self.search_db('''SELECT * FROM %s''' % relation_name)[0]
                length = len(res.keys())

                continuous_features = [0 for f in range(1, length)]
            else:
                raise Exception("Inconsisten DB Exception")

        return continuous_features

    def get_apk_counted_features(self, apk, table_data):

        column_name = table_data['column']
        relation_name = table_data['counted-relation']

        results = {}
        if relation_name:
            query = {'sha256' : apk, 'column' : column_name, 'relation' : relation_name}
            query_result = self.search_db('''select %s, count from %s where apk = :sha256''' % (column_name, relation_name), query)

            for row in query_result:
                results[row[column_name]] = row['count']

        return results

    def get_relevant_features(self, table_data, n_features):
        
        feature_group = table_data['feature-group']
        if feature_group  not in self.relevant_features:
        
            column_name = table_data['column']
            relation_name = table_data['relevant-relation']

            if relation_name:
                query = {'n_features' : n_features}
                query_result = self.search_db('''select %s, count(*) from %s GROUP BY %s ORDER BY count(*) DESC LIMIT :n_features''' % (column_name, relation_name, column_name), query)
                self.relevant_features[feature_group] = [f[column_name] for f in query_result]

        return self.relevant_features[feature_group ]

class MalwareClassificator(BaseEstimator, ClassifierMixin):
    
    # SQL Data
    feature_group_name = None
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

    # Database Manager
    apk_db = APKDatabase()

    def __init__(self):
        pass

    # AI
    def fit(self, dataset):
        
        # Get samples
        samples = self.get_samples(dataset)

        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        training_data, training_labels = self.construct_data(samples, relevant_features)

        # Fit model
        self.model.fit(training_data, training_labels)

    def predict(self, dataset):

        # Get samples
        samples = self.get_samples(dataset)

        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        data, labels = self.construct_data(samples, relevant_features)

        return labels, self.model.predict(data)

    # Performance Eval
    def get_training_results(self, database_file, dataset, cross_validation = 10):

        # Connect DB
        self.apk_db.connect_db(database_file)

        results = []
        # K-Fold Cross Validation
        kf = KFold(n_splits=cross_validation, shuffle = True)
        for train, test in kf.split(dataset):

            # Get training and testing dataset
            training_dataset = [dataset[i] for i in train]
            testing_dataset = [dataset[i] for i in test]

            # Fit model
            self.fit(training_dataset)

            # Predict labels for testing samples
            testing_labels, predicted_labels = self.predict(testing_dataset)

            # Get score
            result = {}
            result['accuracy'] = accuracy_score(testing_labels, predicted_labels, True)
            result['f-score'] = f1_score(testing_labels, predicted_labels)

            results.append(result)

        # Disconnect DB
        self.apk_db.disconnect_db()
        
        return results

    # Feature methods

    def get_samples(self, dataset):

        # Get samples alongside its features in dictionary format
        samples = []
        for apk in dataset:
            sample = self.apk_db.get_apk_data(apk, self.get_table_data())
            samples.append(sample)

        return samples
    
    def get_relevant_features(self):
        return self.apk_db.get_relevant_features(self.get_table_data(), self.n_features)

    # Util

    def construct_data(self, training_samples, relevant_features):

        data = []
        labels = []

        for apk in training_samples:
            self.construct_apk_features(apk, relevant_features, data, labels)

        return data, labels

    def construct_apk_features(self, apk, relevant_features,  data, labels):
        features = []

        # Get features that this classifier needs
        classifier_features = apk[self.feature_group_name]

        # Boolean features
        if classifier_features['boolean-features'] is not None:
            for feature in relevant_features:
                if feature in classifier_features['boolean-features']:
                    features.append(1)
                else:
                    features.append(0)

        # Counted features
        if classifier_features['counted-features'] is not None:
            for feature in relevant_features:
                if feature in classifier_features['counted-features']:
                    features.append(classifier_features['counted-features'][feature])
                else:
                    features.append(0)

        # Continuous features
        if classifier_features['continuous-features'] is not None:
            for feature in classifier_features['continuous-features']:
                features.append(feature)

        # Append to data
        data.append(features)

        # Append to labels
        if 'malware' in apk:
            labels.append(apk['malware'])

    # DB Management

    def get_table_data(self):
        table_data = {}

        table_data['feature-group'] = self.feature_group_name

        table_data['column'] = self.column_name
        table_data['relation'] = self.relation_name
        table_data['counted-relation'] = self.counted_relation_name
        table_data['continuous-relation'] = self.continuous_relation_name
        table_data['relevant-relation'] = self.get_relevant_relation()
    
        return table_data

    def get_relevant_relation(self):
        return self.relation_name

    def get_model(self):
        return self.model

    # Serialization
    def dump_model(self, model_output_file):
    
        if model_output_file:
            dump(self.model, model_output_file)

# Q = 20
class PermissionMalwareClassificator(MalwareClassificator):

    column_name = 'permission'
    feature_group_name = 'permissions'
    relation_name = 'apk_permissions'
    model = BernoulliNB()
    n_features = 20

# Q = 57 (max)
class FunctionalitiesMalwareClassificator(MalwareClassificator):

    column_name = 'functionality'
    tfeature_group_name = 'funtionalities'
    relation_name = 'apk_functionalities'
    model = MultinomialNB()
    n_features = 57

# Q = 8 (max)
class MiscFeatureMalwareClassificator(MalwareClassificator):

    column_name = 'misc_feature'
    feature_group_name = 'misc_features'
    relation_name = 'apk_misc_features'
    continuous_relation_name = 'apk_misc_continuous_features'
    model = GaussianNB()
    n_features = 8        

# Q = 500 (Can be increased, takes much more time)
class StaticFeatureMalwareClassificator(MalwareClassificator):

    column_name = 'static_feature'
    feature_group_name = 'static_features'
    counted_relation_name = 'apk_static_features'
    model = GaussianNB()
    n_features = 500

    def get_relevant_relation(self):
        return self.counted_relation_name

class EnsembledMalwareClassificator(MalwareClassificator):

    classifiers = None
    weights = 0
    weight_map = []

    # Constant
    LIMIT = 100
    STEP = 1

    def __init__(self, classifiers):
        self.classifiers = classifiers

        # Set same database
        for classifier in self.classifiers:
            classifier.apk_db = self.apk_db

        self.weight_map = self.gen_weight_map()

    def fit(self, dataset):
        for classifier in self.classifiers:
            classifier.fit(dataset)

    def predict(self, dataset):
        # Get malware types
        labels = [self.apk_db.get_apk_type(apk) for apk in dataset]

        # Get prediction
        predictions = np.column_stack([classifier.predict(dataset)[1] for classifier in self.classifiers])

        weights = [v/100 for v in self.get_weights(self.weights)]
        assert sum(weights) == 1

        prediction_values = []
        for pred in predictions:
            pvalue = 0
            for i in range(0, len(self.classifiers)):
                if pred[i]:
                    pvalue = pvalue + weights[i]
            prediction_values.append(pvalue)

        prediction_labels = [value >= 0.5 for value in prediction_values]

        return labels, prediction_labels
    
    def get_weights(self, index):
        return self.weight_map[index]

    def gen_weight_map(self):
        N = len(self.classifiers)
        weight_map = self.get_n_weight_combinations(N, self.LIMIT, self.STEP)
        return weight_map

    def get_n_weight_combinations(self, N, limit, step):

        if N < 2:
            return

        if N == 2:
            return self.get_2_weight_combinations(limit, step)

        box = limit + step

        o_vectors = []
        while box != 0:
            box = box - step
            rest = limit - box

            next = N - 1
            i_vectors = self.get_n_weight_combinations(next, rest, step)

            for v in i_vectors:
                o_vector = [box]
                
                for coord in v:
                    o_vector.append(coord)

                o_vectors.append(o_vector)

        return o_vectors

    def get_2_weight_combinations(self, limit, step):

        boxes = [0, 0]
    
        c_index = 0
        o_index = 1

        boxes[c_index] = limit + step
        boxes[o_index] = -step

        results = []
        while boxes[c_index] != 0:
    
            boxes[c_index] = boxes[c_index] - step
            boxes[o_index] = limit - boxes[c_index]

            v = [boxes[c_index], boxes[o_index]]
            results.append(v)

        return results
    
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
    elif feature_key == 'e':
        classifier = EnsembledMalwareClassificator([MiscFeatureMalwareClassificator(), PermissionMalwareClassificator()])
    else:
        argparser.error("Unrecognized classificator identifier")

    # Set params
    classifier.n_features = n_permissions

    # TODO - Get APK list to use as dataset
    dbclient = SQL3Client()
    dbclient.connect(database_file)
    dbclient.execute('''SELECT * FROM apks WHERE downloaded = 1''')
    results = dbclient.fetchall()
    dataset = [row['sha256'] for row in results]
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