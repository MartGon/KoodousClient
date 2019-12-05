
from DatabaseMgr.SQL3Client import *
from DatasetTrainer import construct_data, get_relevant_permissions

from sklearn.naive_bayes import MultinomialNB
from joblib import dump, load

import argparse
import androguard.core.bytecodes.apk

def main():

    # Configure argparser
    argparser = argparse.ArgumentParser(description='Verify Apk')
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--model-input-file', '-mif', help='Model input file location for loading', required=True)
    argparser.add_argument('--apk', '-a', help="APK input file", required=True)

    # Parse args
    args = argparser.parse_args()
    db_file = args.database_file

    # Load model
    mnnb = load(args.model_input_file)

    # Get APK features
    apk = androguard.core.bytecodes.apk.APK(args.apk)
    permissions = apk.get_permissions()

    # Open Database
    dbclient = SQL3Client()
    dbclient.connect(db_file)

    # Get top permissions
    top_permissions = get_relevant_permissions(dbclient, 20)

    # Construct data for this sample
    sample = dict()
    sample['permissions'] = [get_permission_id(dbclient, info) for info in permissions]
    samples = [sample]
    data, _ = construct_data(samples, top_permissions)

    # Make prediction
    result = mnnb.predict(data)[0]
    chance_vector = mnnb.predict_proba(data)[0]

    print("Probability vector: (%0.2f, %0.2f)" % (chance_vector[0], chance_vector[1]))

    tag = "Malware" if result == 1 else "Goodware"
    print("This application is probably %s" % tag)

    # Close connection
    dbclient.close()

def get_permission_id(dbclient, permission_str):

    # Execute query
    query = {'info' : permission_str}
    dbclient.execute('''SELECT id FROM permissions WHERE info = :info''', query)
    
    # Fetch result
    result = dbclient.fetchone()
    id = result['id']

    return id
    
if __name__ == '__main__':
    main()
