from DatabaseMgr.DatabaseMgr import *

from sklearn.base import BaseEstimator
from sklearn.base import ClassifierMixin

from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import GaussianNB
from sklearn.naive_bayes import BernoulliNB

from sklearn.ensemble import AdaBoostClassifier
from sklearn.ensemble import RandomForestClassifier

from sklearn.model_selection import KFold
from sklearn.model_selection import RandomizedSearchCV
from sklearn.model_selection import GridSearchCV

from sklearn.metrics.classification import accuracy_score
from sklearn.metrics.classification import f1_score

from sklearn.svm import SVC

from sklearn.neighbors import KNeighborsClassifier

from sklearn.tree import DecisionTreeClassifier

from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF

from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis

from sklearn.neural_network import MLPClassifier

from scipy.stats import uniform

from random import shuffle, choice, randrange
from joblib import dump, load

import argparse
import numpy as np

import concurrent.futures

from math import ceil, floor

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
        
        features = str(n_features)

        feature_group = table_data['feature-group']
        if feature_group not in self.relevant_features:
            self._get_relevant_features(table_data, n_features)
        elif features not in self.relevant_features[feature_group]:
            self._get_relevant_features(table_data, n_features)

        return self.relevant_features[feature_group][features]

    def _get_relevant_features(self, table_data, n_features):
        features = str(n_features)
        feature_group = table_data['feature-group']
        column_name = table_data['column']
        relation_name = table_data['relevant-relation']

        if relation_name:
            query = {'n_features' : n_features}
            query_result = self.search_db('''select %s, count(*) from %s GROUP BY %s ORDER BY count(*) DESC LIMIT :n_features''' % (column_name, relation_name, column_name), query)
            self.relevant_features[feature_group] = {}
            self.relevant_features[feature_group][features] = [f[column_name] for f in query_result]

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
    features = 50

    # Caches
    relevant_features = []
    cached_apk_features = {}
    last_score = -1

    # Database Manager
    apk_db = APKDatabase()

    def __init__(self, model=None, features=0):
        self.model = model
        self.features = features

    # AI
    def fit(self, dataset, Y = None):
        
        # Get samples
        samples = self.get_samples(dataset)

        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        training_data, training_labels = self.construct_data(samples, relevant_features)

        # Fit model
        self.model.fit(training_data, training_labels)

    def i_predict(self, dataset):

        # Get samples
        samples = self.get_samples(dataset)

        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        data, labels = self.construct_data(samples, relevant_features)

        return labels, self.model.predict(data)

    def predict(self, dataset):
        return self.i_predict(dataset)[1]

    # Returns [P(X=0), P(X=1)]
    def predict_proba(self, dataset):

        # Get samples
        samples = self.get_samples(dataset)

        # Get relevant_features
        relevant_features = self.get_relevant_features()

        # Construct training data
        data, labels = self.construct_data(samples, relevant_features)

        return self.model.predict_proba(data)

    def i_predict_proba(self, dataset):
        return [p[0] for p in self.predict_proba(dataset)]

    # Performance Eval
    def get_training_results(self, database_file, dataset, cross_validation = 10):

        # Connect DB
        self.apk_db.connect_db(database_file)

        results = []
        # K-Fold Cross Validation
        kf = KFold(n_splits=cross_validation, shuffle = False)
        for train, test in kf.split(dataset):

            # Get training and testing dataset
            training_dataset = [dataset[i] for i in train]
            testing_dataset = [dataset[i] for i in test]

            # Fit model
            self.fit(training_dataset)

            # Predict labels for testing samples
            testing_labels, predicted_labels = self.i_predict(testing_dataset)

            # Get score
            result = {}
            result['accuracy'] = accuracy_score(testing_labels, predicted_labels, True)
            result['f-score'] = f1_score(testing_labels, predicted_labels)

            results.append(result)

        # Disconnect DB
        self.apk_db.disconnect_db()

        accuracy_avg = round(sum([f['accuracy'] for f in results]) / len(results) * 100, 2)
        f_score_avg = round(sum([f['f-score'] for f in results]) / len(results) * 100, 2)

        return accuracy_avg, f_score_avg

    def get_score(self, database_file, dataset, cross_validation = 10):

        if self.last_score == -1:
            accuracy, f_score = self.get_training_results(database_file, dataset, cross_validation);
            # self.last_score = (accuracy + f_score) / 2
            self.last_score = accuracy

        return self.last_score

    # Feature methods
    def get_samples(self, dataset):

        # Get samples alongside its features in dictionary format
        samples = []
        for apk in dataset:
            sample = self.apk_db.get_apk_data(apk, self.get_table_data())
            samples.append(sample)

        return samples
    
    def get_relevant_features(self):
        return self.apk_db.get_relevant_features(self.get_table_data(), self.features)

    # Util

    def construct_data(self, training_samples, relevant_features):

        data = []
        labels = []
        for apk in training_samples:
            features = self.construct_apk_features(apk, relevant_features)
            data.append(features)
            labels.append(apk['malware'])

        return data, labels

    def construct_apk_features(self, apk, relevant_features):

        features = []

        n_rfeatures_key = str(len(relevant_features))
        sha256 = apk['sha256']
        if sha256 not in self.cached_apk_features:
            self.cached_apk_features[sha256] = {}
            features = self._construct_feature_vector(apk, relevant_features)
            self.cached_apk_features[sha256][n_rfeatures_key] = features
        elif n_rfeatures_key not in self.cached_apk_features[sha256]:
            features = self._construct_feature_vector(apk, relevant_features)
            self.cached_apk_features[sha256][n_rfeatures_key] = features
        else:
            features = self.cached_apk_features[sha256][n_rfeatures_key]
        
        return features

    def _construct_feature_vector(self, apk, relevant_features):
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

        return features

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

    # Loading
    def load_model(self, model_input_file):

        if model_input_file:
            self.model = load(model_input_file)

# Q = 40
# Model = RandomForesClassifier()
class PermissionMalwareClassificator(MalwareClassificator):

    column_name = 'permission'
    feature_group_name = 'permissions'
    relation_name = 'apk_permissions'

    def __init__(self, model=RandomForestClassifier(n_estimators=100), features = 40):
        super().__init__(model, features)

# Q = 40 (max)
# Model = GaussianProcessClassifier()
class FunctionalitiesMalwareClassificator(MalwareClassificator):

    column_name = 'functionality'
    tfeature_group_name = 'funtionalities'
    relation_name = 'apk_functionalities'

    def __init__(self, model=GaussianProcessClassifier(), features = 40):
        super().__init__(model, features)

# Q = 8 (max)
# Model = RandomForestClassifier()
class MiscFeatureMalwareClassificator(MalwareClassificator):

    column_name = 'misc_feature'
    feature_group_name = 'misc_features'
    relation_name = 'apk_misc_features'
    continuous_relation_name = 'apk_misc_continuous_features'

    def __init__(self, model=RandomForestClassifier(n_estimators=100), features = 8):
        super().__init__(model, features)     

# Q = 5120 (Can be increased, takes much more time)
# Model = RamdomForestClassifier()
class StaticFeatureMalwareClassificator(MalwareClassificator):

    column_name = 'static_feature'
    feature_group_name = 'static_features'
    counted_relation_name = 'apk_static_features'

    def __init__(self, model=RandomForestClassifier(n_estimators=100), features = 5120):
        super().__init__(model, features)   

    def get_relevant_relation(self):
        return self.counted_relation_name

# W = 81711
# W = 41916
class EnsembledMalwareClassificator(MalwareClassificator):

    weight_map = []

    class EnsembledData:

        def __init__(self, classifiers, weights):

            self.classifiers = classifiers
            self.weights = weights

    # Constant
    LIMIT = 100
    STEP = 1

    def __init__(self, classifiers=[PermissionMalwareClassificator(), MiscFeatureMalwareClassificator(), FunctionalitiesMalwareClassificator(), StaticFeatureMalwareClassificator()], weights=41916):
        self.classifiers = classifiers

        # Set same database
        for classifier in self.classifiers:
            classifier.apk_db = self.apk_db

        if len(self.weight_map) < 1:
            EnsembledMalwareClassificator.weight_map = EnsembledMalwareClassificator.gen_weight_map(classifiers)

        self.weights = weights

    # Need to add a Y parameter in order to use scikit learn parameter optmization
    def fit(self, dataset, Y = None):
        for classifier in self.classifiers:
            classifier.fit(dataset)

    def i_predict_proba(self, dataset):
        # Get malware types
        labels = [self.apk_db.get_apk_type(apk) for apk in dataset]

        # Get prediction
        predictions = np.column_stack([classifier.i_predict_proba(dataset) for classifier in self.classifiers])
        weights = [v for v in self.weights]
        assert round(sum(weights)) == EnsembledMalwareClassificator.LIMIT

        prediction_values = []
        for pred in predictions:
            pvalue = 0
            for i in range(0, len(self.classifiers)):
                pvalue = pvalue + (weights[i]/EnsembledMalwareClassificator.LIMIT) * (1 - pred[i])

            prediction_values.append([1 - pvalue, pvalue])

        return labels, prediction_values

    def i_predict(self, dataset):
        labels, prediction_values = self.i_predict_proba(dataset)

        prediction_labels = [value[1] >= 0.5 for value in prediction_values]

        return labels, prediction_labels

    def predict(self, dataset):
        return self.i_predict(dataset)[1]
    
    def predict_proba(self, dataset):
        return self.i_predict_proba(dataset)[1]

    def get_weights(index):
        return EnsembledMalwareClassificator.weight_map[int(index)]

    def gen_weight_map(classifiers):
        N = len(classifiers)
        weight_map = EnsembledMalwareClassificator.get_n_weight_combinations(N, EnsembledMalwareClassificator.LIMIT, EnsembledMalwareClassificator.STEP)
        return weight_map

    def get_n_weight_combinations(N, limit, step):

        if N < 2:
            return

        if N == 2:
            return EnsembledMalwareClassificator.get_2_weight_combinations(limit, step)

        box = limit + step

        o_vectors = []
        while box != 0:
            box = box - step
            rest = limit - box

            next = N - 1
            i_vectors = EnsembledMalwareClassificator.get_n_weight_combinations(next, rest, step)

            for v in i_vectors:
                o_vector = [box]
                
                for coord in v:
                    o_vector.append(coord)

                o_vectors.append(o_vector)

        return o_vectors

    def get_2_weight_combinations(limit, step):

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
    
    def dump_model(self, model_output_file):
        cdata = self.EnsembledData(self.classifiers, self.weights)
        dump(cdata, model_output_file)

    def load_model(self, model_input_file):
        cdata = load(model_input_file)

        self.__init__(cdata.classifiers, cdata.weights)


class Individual:
    pass

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--feature-key', '-fk', help = 'Features that will be used for training can be (p, f, m, s, e)', required=True)
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--quantity', '-q', help = 'Number of top used features to employ', required=False, default=5, type=int)
    argparser.add_argument('--cross-validation', '-cv', help='Cross Validation iterations', required=False, default=10, type=int)
    argparser.add_argument('--csv-output-file', '-csv', help='CSV output file for results', required=False)
    argparser.add_argument('--model-output-file', '-mof', help='Model output file location for dumping', required=False)
    argparser.add_argument('--optimize-hyperparams', '-oh', help='Whether to optimize hyper params', required=False, action='store_true', dest='optimize')
    argparser.add_argument('--no-optimize-hyperparams', '-noh', help='Whether to optimize hyper params', required=False, action='store_false', dest='optimize')
    
    argparser.add_argument('--population', '-p', help = 'Population size', required=False, default=10, type=int)
    argparser.add_argument('--epochs', '-e', help = 'Epochs', required=False, default=10, type=int)
    argparser.add_argument('--candidates', '-c', help = 'Number of individuals which reproduce. Produce candidates / 2 offsprins', required=False, default=4, type=int)

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
        classifier = EnsembledMalwareClassificator()
    else:
        argparser.error("Unrecognized classificator identifier")

    # Set paramsprint(
    # classifier.n_features = n_permissions

    # TODO - Get APK list to use as dataset
    dbclient = SQL3Client()
    dbclient.connect(database_file)
    dbclient.execute('''SELECT * FROM apks WHERE downloaded = 1''')
    results = dbclient.fetchall()
    dataset = [row['sha256'] for row in results]
    shuffle(dataset)
    dbclient.close()

    # Get training results
    #accuracy_avg, f_score_avg  = classifier.get_training_results(database_file, dataset, args.cross_validation)

    print()
    #print("Info: Accuracy = %f" % accuracy_avg)
    #print("Info: F-Score = %f" % f_score_avg)

    # Write csv results
    #write_results(results, args.csv_output_file, accuracy_avg, f_score_avg)

    # Dump model
    #classifier.dump_model(args.model_output_file)
    #classifier.load_model(args.model_output_file)

    classifier.apk_db.connect_db(database_file)
    #print(classifier.predict_proba(["df38039bb21d9ed1a0bf11b9bb2e4c77594e93e3be0ec7d20b830395dd9abb96"]))

    if args.optimize:

        # Cache weight_map
        weight_map = classifier.weight_map

        # Create initial population
        population = []
        for i in range(0, args.population):
            chosen_weight = weight_map[choice(range(0, len(weight_map)))]
            o_classifier = EnsembledMalwareClassificator(weights=chosen_weight)
            population.append(o_classifier)            

        # Main loop
        current_epoch = 0
        while(current_epoch < args.epochs):
            
            # Get scores
            for i_classifier in population:
                score = i_classifier.get_score(database_file, dataset, args.cross_validation)
                print("Weight (%s): %f score" % (i_classifier.weights, score))

            # Sort by score
            population.sort(key=lambda x:x.last_score, reverse=True)

            current_epoch = current_epoch + 1
            if current_epoch > args.epochs:
                break

            # Remove worsts
            population_new_size = round(len(population) - (args.candidates / 2))
            population = population[0:population_new_size]

            # Reproduce
            for i in range(0, args.candidates, 2):
                w_indexA = population[i].weights
                w_indexB = population[i + 1].weights

                new_weight = reproduce(w_indexA, w_indexB)
                offspring_weight = normalize(mutate(new_weight))
                print("Offsrping Weight (%s)" % (offspring_weight))

                n_classifier = EnsembledMalwareClassificator(weights= offspring_weight)
                population.append(n_classifier)

            print()
            print()              

        print("The best score is %f for weights %s " % (population[0].last_score, population[0].weights))

        return

def sum_weights(a, b):

    assert len(a) == len(b)

    weights = []
    for i in range(0, len(a)):
        c = a[i] + b[i]
        weights.append(c)

    return weights

def normalize(vec):

    size = 0
    for num in vec:
        size = size + num

    n_vec = []

    for num in vec:
        member = (num / size) * 100
        n_vec.append(member)

    return n_vec

# Mutation is simply an average of both weights
def reproduce(a, b):

    summed_w = sum_weights(a, b)

    avg_w = []
    for i in range(0, len(summed_w)):
        avg_w.append(summed_w[i] / 2)

    return avg_w

def mutate_alt(weights):
    index = randrange(0, len(weights))

    vec = list(range(0, len(weights)))
    vec[index] = EnsembledMalwareClassificator.LIMIT

    return reproduce(weights, vec)

def mutate(weights):
    
    mutation_size = randrange(10, 25)

    for i in range(0, mutation_size):
        index = randrange(0, len(weights))

        weights[index] = weights[index] + 1
    
    return weights

     
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

def write_search_results(results, file_location):

    if file_location is not None:

        dir = os.path.dirname(file_location)
        name = os.path.basename(file_location)
        new_name = "hyper-" + name
        filename = os.path.join(dir, new_name)

        file = open(filename, "w")

        # Write file header
        params = results['params']
        header = ""
        for param in params[0]:
            header = header + param + ", "
        header = header + "Mean Score\n"
        file.write(header)
        
        # Write scores
        scores = results['mean_test_score']
        tests_len = len(scores)
        for i in range(0, tests_len):
            row = ""
            for param in params[i]:
                string = str(params[i][param])

                # Substring if is a model name
                char = '('
                if char in string:
                    n = string.find('(')
                    string = string[:n]

                row = row + string + ", "
            row = row + str(round(scores[i], 4)) + "\n"
            file.write(row)

        file.close()
        

if __name__ == '__main__':
    main()