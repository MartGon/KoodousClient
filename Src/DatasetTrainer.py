from DatabaseMgr.DatabaseMgr import *

from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import KFold
from random import shuffle
from joblib import dump, load

import argparse

class MalwareClassificator(DatabaseManager):
    
    column_name = None
    table_name = None

    model = None

    def __init__(self):
        pass

    def get_training_results(self, database_file, cross_validation, n_features):
        
        # Connect to DB
        self.connect_db(database_file)
        
        # Get every sample which is downloaded
        query_result = self.search_db('''SELECT * FROM apks WHERE downloaded = 1''')

        # Get samples alongside its features in dictionary format
        samples = []
        for apk in query_result:
            sample = {}

            # Get main data
            sample['sha256'] = apk['sha256'] 
            sample['malware'] = apk['malware']

            # Get APK features
            column_name = self.get_column()
            relation_name = self.get_relation()
            table_name = self.get_table()

            query = {'sha256' : apk['sha256'], 'column' : column_name, 'relation' : relation_name}
            query_result = self.search_db('''select %s from %s where apk = :sha256''' % (column_name, relation_name), query)
            sample[table_name] = [f[column_name] for f in query_result]

            samples.append(sample)

        shuffle(samples)

        # Get relevant features
        top_features = self.get_relevant_features(n_features)

        # Close DB Connection
        self.disconnect_db()

        # K-Fold Cross Validation
        kf = KFold(n_splits=cross_validation)

        # Calculate results
        results = []
        for train, test in kf.split(samples):

            # Get training and testing samples from index
            training_samples = [samples[i] for i in train]
            testing_samples = [samples[i] for i in test]

            # Construct training and testing data in scikit learn format
            training_data, training_labels = self.construct_data(training_samples, top_features)
            testing_data, testing_labels = self.construct_data(testing_samples, top_features)

            # Train model with training data
            model = MultinomialNB()
            model.fit(training_data, training_labels)

            # Predict labels for testing samples
            predicted_labels = model.predict(testing_data)

            # Accuracy assessment
            assert(len(predicted_labels) == len(testing_labels))

            false_positives = 0
            false_negatives = 0
            true_positives = 0
            true_negatives = 0
            for i in range(0, len(predicted_labels)):
                if predicted_labels[i] == testing_labels[i]:                
                    if predicted_labels[i] == 1:
                        true_positives = true_positives + 1
                    else:
                        true_negatives = true_negatives + 1
                elif predicted_labels[i] == 1:
                    false_positives = false_positives + 1
                elif predicted_labels[i] == 0:
                    false_negatives = false_negatives + 1

            # Store results
            result = {}
            result['fp'] = false_positives
            result['fn'] = false_negatives
            result['tp'] = true_positives
            result['tn'] = true_negatives
            
            # Convenience
            result['accuracy'] = round((result['tp'] + result['tn'])/ len(predicted_labels), 2)

            p_div = (result['tp'] + result['fp']) if (result['tp'] + result['fp']) > 0 else 0.01
            r_div = (result['tp'] + result['fn']) if (result['tp'] + result['fn']) > 0 else 0.01

            result['precision'] = round(result['tp']/(p_div), 2)
            result['recall'] = round(result['tp']/(r_div), 2)

            f_div = (result['precision'] + result['recall']) if (result['precision'] + result['recall']) > 0 else 0.01
            result['f-score'] = round((2 * result['precision'] * result['recall']) / (f_div), 2)

            results.append(result)
        
        return results

    def get_relevant_features(self, n_features):

        column_name = self.get_column()
        relation_name = self.get_relation()

        query = {'n_features' : n_features}
        query_result =self.search_db('''select %s, count(*) from %s GROUP BY %s ORDER BY count(*) DESC LIMIT :n_features''' % (column_name, relation_name, column_name), query)
        top_features = [f[column_name] for f in query_result]

        return top_features

    def construct_data(self, training_samples, top_features):

        table_name = self.get_table()

        data = []
        labels = []
        for apk in training_samples:        
            features = []
            for feature in top_features:
                if feature in apk[table_name]:
                    features.append(1)
                else:
                    features.append(0)

            data.append(features)
            if 'malware' in apk:
                labels.append(apk['malware'])

        return data, labels

    def get_column(self):
        return self.column_name
    
    def get_table(self):
        return self.table_name

    def get_relation(self):
        return self.relation_name
    
    def dump_model(self, model_output_file):
    
        if model_output_file:
            dump(self.model, model_output_file)

class PermissionMalwareClassificator(MalwareClassificator):

    column_name = 'permission'
    table_name = 'permissions'
    relation_name = 'apk_permissions'

class FunctionalitiesMalwareClassificator(MalwareClassificator):

    column_name = 'functionality'
    table_name = 'funtionalities'
    relation_name = 'apk_functionalities'

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--feature-key', '-fk', help = 'Features that will be used for training can be (p, f)', required=True)
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--permissions', '-p', help = 'Number of top used permissions to use as features', required=False, default=5, type=int)
    argparser.add_argument('--cross-validation', '-cv', help='Cross Validation iterations', required=False, default=10, type=int)
    argparser.add_argument('--csv-output-file', '-csv', help='CSV output file for results', required=False)
    argparser.add_argument('--model-output-file', '-mof', help='Model output file location for dumping', required=False)

    # Parse arguments
    args = argparser.parse_args()
    database_file = args.database_file
    n_permissions = args.permissions
    feature_key = args.feature_key

    # Create classifier
    classifier = None
    if feature_key == 'p':
        classifier = PermissionMalwareClassificator()
    elif feature_key == 'f':
        classifier = FunctionalitiesMalwareClassificator()
    else:
        argparser.error("Unrecognized classificator identifier")

    # Get training results
    results = classifier.get_training_results(database_file, args.cross_validation, n_permissions)

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