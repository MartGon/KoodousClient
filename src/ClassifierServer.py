
from DatabaseMgr.SQL3Client import *
from DatasetTrainer import *
from DatasetMgr.DBDatasetUpdater import DBDatasetUpdater
from DatasetMgr.FeatureMgr import FullUpdater, FeatureManager

from sklearn.naive_bayes import MultinomialNB
from joblib import dump, load

import argparse
import socket
import json
import traceback
import androguard.core.bytecodes.apk

class ClassifierServer:

    def __init__(self, database_file, model_input_file, port):
        self.database_file = database_file
        self.classifier = EnsembledMalwareClassificator([])
        if model_input_file:
            self.classifier.load_model(model_input_file)
        else:
            self._train_model()
        self.port = port

        self.updater = DBDatasetUpdater()
        self.feature_mgr = FeatureManager("x")

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("localhost", self.port))

    def _train_model(self):
        self.classifier = EnsembledMalwareClassificator()
        self.classifier.apk_db.connect_db(self.database_file)

        results = self.classifier.apk_db.search_db('SELECT * FROM apks WHERE downloaded = 1')
        dataset = [row['sha256'] for row in results]
        self.classifier.fit(dataset)
        self.classifier.apk_db.disconnect_db()

    def update_db(self, apk):
        self.updater.connect_db(self.database_file)
        sha256 = self.updater.update_db_apk(apk)
        self.updater.disconnect_db()
        return sha256
    
    def update_features_db(self, apk):
        self.feature_mgr.connect_db(self.database_file)
        self.feature_mgr.update_db_apk(apk)
        self.feature_mgr.disconnect_db()

    def make_prediction(self, sha256):
        self.classifier.apk_db.connect_db(self.database_file)

        input = [sha256]
        result = self.classifier.predict(input)[0]
        chance_vector = self.classifier.predict_proba(input)[0]

        self.classifier.apk_db.disconnect_db()

        return int(result), chance_vector

    def verify_apk(self, apk):
        # Update DB with this apk data
        sha256 = self.update_db(apk)
        self.update_features_db(apk)

        return self.make_prediction(sha256)

def main():

    # Configure argparser
    argparser = argparse.ArgumentParser(description='Verify Apk')
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--model-input-file', '-mif', help='Model input file location for loading', required=False, default = None)
    argparser.add_argument('--apk', '-a', help="APK input file", required=False)
    argparser.add_argument('--port', '-p', help="Server port to listen for requests", required=False, default=3000, type=int)

    # Parse args
    args = argparser.parse_args()
    database_file = args.database_file

    server = ClassifierServer(database_file, args.model_input_file, args.port)

    print("Server listening on %s for incoming connection on port %i" % ("localhost", args.port))
    server.socket.listen(1)
    try:
        while True:

            (client_socket, address) = server.socket.accept()
            print("Connection accepted from %s" % address[0])

            while client_socket:

                request = client_socket.recv(4096)
                if request:
                    print("Request recv")
                    request_data = json.loads(request)
                    apk_path = request_data['path']

                    response = {}
                    response['prediction'], response['prob'] = server.verify_apk(apk_path)
                    json_response = json.dumps(response)
                    print("Send response")
                    client_socket.send(str.encode(json_response))
                else:
                    print("Peer disconnected")
                    client_socket = None
                    break
    except Exception as err:
        traceback.print_exc()
        print()
        print("Closing server")
        client_socket.close()
        server.socket.close()


    
if __name__ == '__main__':
    main()
