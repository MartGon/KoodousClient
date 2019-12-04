from DatabaseMgr.SQL3Client import *

from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import GaussianNB
from random import shuffle

import argparse

TRAINING_PERCENTAGE = 0.75

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--permissions', '-p', help = 'Number of top used permissions to use as features', required=False, default=5, type=int)
    argparser.add_argument('--training_rate', '-tr', help = 'Rate of samples that would be used for training', required=False, default = TRAINING_PERCENTAGE, type=float)
    argparser.add_argument('--include-permission-n', '-ipn', help = 'Whether to include the number of permissions declared as features', required=False, default=False, type=int)

    # Parser arguments
    args = argparser.parse_args()
    database_file = args.database_file
    n_permissions = args.permissions
    training_rate = args.training_rate
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

    # Get dataset data
    malware = [f for f in samples if f['malware'] == 1]
    goodware = [f for f in samples if f['malware'] == 0]

    #
    shuffle(malware)
    shuffle(goodware)

    # Split into training and trial
    training_malware, trial_malware = split_samples(malware, training_rate)
    training_goodware, trial_goodware = split_samples(goodware, training_rate)

    training_samples = training_malware + training_goodware
    testing_samples = trial_malware + trial_goodware

    # Get top X permissions
    dbclient.execute('''select permission, count(*) from apk_permissions INNER JOIN apks ON apk = sha256 WHERE malware = 0 GROUP BY permission ORDER BY count(*) DESC LIMIT :n_permissions''', {'n_permissions' : n_permissions})
    query_result = dbclient.fetchall()
    top_permissions = [f['permission'] for f in query_result]

    # Close DB Connection
    dbclient.close()

    # Construct training data in scikit learn format
    training_data, training_labels = construct_data(training_samples, top_permissions, include_permission_n)

    # Construct testing data in scikit learn format
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
    for i in range(0, len(predicted_labels)):
        if predicted_labels[i] == testing_labels[i]:
            hits = hits + 1
        elif predicted_labels[i] == 1:
            false_positives = false_positives + 1
        elif predicted_labels[i] == 0:
            false_negatives = false_negatives + 1

    print("Info: %i/%i Hits" % (hits, len(predicted_labels)))
    print("Info: %i/%i False Positives" % (false_positives, len(predicted_labels)))
    print("Info: %i/%i False Negatives" % (false_negatives, len(predicted_labels)))

    mistakes = len(predicted_labels) - hits
    accuracy = round(hits / len(predicted_labels), 2) * 100
    fp_ratio = round(false_positives / mistakes, 2)
    fn_ratio = round(false_negatives / mistakes, 2)
    print("Info: Accuracy = %f" % accuracy)
    print("Info: False Positive ratio = %f" % fp_ratio)
    print("Info: False Negative ratio = %f" % fn_ratio)

def split_samples(samples, split_percent):

    samples_index = int(len(samples) * split_percent)
    training_samples = samples[:samples_index]
    trial_samples = samples[samples_index:]

    return training_samples, trial_samples

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


if __name__ == '__main__':
    main()