from DatabaseMgr.SQL3Client import *

from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import KFold
from random import shuffle

import argparse

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--permissions', '-p', help = 'Number of top used permissions to use as features', required=False, default=5, type=int)
    argparser.add_argument('--include-permission-n', '-ipn', help = 'Whether to include the number of permissions declared as features', required=False, default=False, type=int)
    argparser.add_argument('--cross-validation', '-cv', help='Cross Validation iterations', required=False, default=10, type=int)
    argparser.add_argument('--csv-output-file', '-csv', help='CSV output file for results', required=False)

    # Parse arguments
    args = argparser.parse_args()
    database_file = args.database_file
    n_permissions = args.permissions
    include_permission_n = args.include_permission_n

    # Create and connect DB client
    dbclient = SQL3Client()
    dbclient.connect(database_file)

    # Get every sample which is downloaded
    dbclient.execute('''SELECT * FROM apks WHERE downloaded = 1''')
    query_result = dbclient.fetchall()

    # Get samples alongside its permissions in dictionary format
    samples = []
    for apk in query_result:
        sample = {}

        # Get main data
        sample['sha256'] = apk['sha256'] 
        sample['malware'] = apk['malware']

        # Get Permissions
        dbclient.execute('''select permission from apk_permissions where apk = :sha256''', {'sha256' : apk['sha256']})
        query_result = dbclient.fetchall()
        sample['permissions'] = [f['permission'] for f in query_result]

        samples.append(sample)

    shuffle(samples)

    # Get top X permissions
    #dbclient.execute('''select permission, count(*) from apk_permissions INNER JOIN apks ON apk = sha256 WHERE malware = 0 GROUP BY permission ORDER BY count(*) DESC LIMIT :n_permissions''', {'n_permissions' : n_permissions})
    #dbclient.execute('''select permission, count(*) from apk_permissions INNER JOIN apks ON apk = sha256 WHERE malware = 1 GROUP BY permission ORDER BY count(*) DESC LIMIT :n_permissions''', {'n_permissions' : n_permissions})
    dbclient.execute('''select permission, count(*) from apk_permissions GROUP BY permission ORDER BY count(*) DESC LIMIT :n_permissions''', {'n_permissions' : n_permissions})
    query_result = dbclient.fetchall()
    top_permissions = [f['permission'] for f in query_result]

    # Close DB Connection
    dbclient.close()

    # K-Fold Cross Validation
    kf = KFold(n_splits=args.cross_validation)

    # Calculate results
    results = []
    for train, test in kf.split(samples):

        # Get training and testing samples from index
        training_samples = [samples[i] for i in train]
        testing_samples = [samples[i] for i in test]

        # Construct training and testing data in scikit learn format
        training_data, training_labels = construct_data(training_samples, top_permissions, include_permission_n)
        testing_data, testing_labels = construct_data(testing_samples, top_permissions, include_permission_n)

        # Train model with training data
        gnb = MultinomialNB()
        gnb.fit(training_data, training_labels)

        # Predict labels for testing samples
        predicted_labels = gnb.predict(testing_data)

        # Accuracy assessment
        assert(len(predicted_labels) == len(testing_labels))

        hits = 0
        false_positives = 0
        false_negatives = 0
        true_positives = 0
        true_negatives = 0
        for i in range(0, len(predicted_labels)):
            if predicted_labels[i] == testing_labels[i]:
                hits = hits + 1
                
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
        result['precision'] = round(result['tp']/(result['tp'] + result['fp']), 2)
        result['recall'] = round(result['tp']/(result['tp'] + result['fn']), 2)
        result['f-score'] = round((2 * result['precision'] * result['recall']) / (result['precision'] + result['recall']), 2)

        results.append(result)
        print(result)

    # Get Measures
    accuracy_avg = round(sum([f['accuracy'] for f in results]) / len(results) * 100, 2)
    f_score_avg = round(sum([f['f-score'] for f in results]) / len(results) * 100, 2)

    # Write results
    write_results(results, args.csv_output_file)

    print()
    print("Info: Accuracy = %f" % accuracy_avg)
    print("Info: F-Score = %f" % f_score_avg)
        
def construct_data(training_samples, top_permissions, do_add_permission_n = 0):

    data = []
    labels = []
    for apk in training_samples:        
        features = []
        for permission in top_permissions:
            if permission in apk['permissions']:
                features.append(1)
            else:
                features.append(0)

        if do_add_permission_n == 1:
            permission_n = int(len(apk['permissions'])/5)
            features.append(permission_n)

        data.append(features)
        labels.append(apk['malware'])

    return data, labels

def write_results(results, file_location):

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
        accuracy_avg = round(sum([f['accuracy'] for f in results]) / len(results) * 100, 2)
        f_score_avg = round(sum([f['f-score'] for f in results]) / len(results) * 100, 2)
        row = "Total, %f, %f \n" %(accuracy_avg, f_score_avg)

        file.write(row)

        file.close()


if __name__ == '__main__':
    main()