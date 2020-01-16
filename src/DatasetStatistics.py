
from DatabaseMgr.DatabaseMgr import *

import matplotlib.pyplot as plt
import argparse

class FeatureStatExtractor(DatabaseManager):

    def get_data(self, database_file, quantity):
        self.connect_db(database_file)
    
        # Get data
        statement = ('''select id, info, count(*) as freq from %s INNER JOIN %s ON %s = id group by %s ORDER BY count(*) DESC LIMIT :quantity''' 
        % (self.get_relation_name(), self.get_table_name(), self.get_column_name(), self.get_column_name()))
        rows = self.search_db(statement, {'quantity':quantity})

        self.disconnect_db()

        return rows
    
    def get_relation_name(self):
        return self.relation_name

    def get_table_name(self):
        return self.table_name
    
    def get_column_name(self):
        return self.column_name

class PermissionStatExtractor(FeatureStatExtractor):

    relation_name = "apk_permissions"
    table_name = "permissions"
    column_name = "permission"

class FunctionalityStatExtractor(FeatureStatExtractor):

    relation_name = "apk_functionalities"
    table_name = "functionalities"
    column_name = "functionality"

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--quantity', '-q', help = 'Amount of values to show in the histogram', default = 10, type=int)
    argparser.add_argument('--feature-key', '-fk', help = 'Feature from which extract stats', required=True)
    
    # Parser arguments
    args = argparser.parse_args()
    database_file = args.database_file
    quantity = args.quantity
    feature_key = args.feature_key

    fse = None
    if feature_key == "p":
        fse = PermissionStatExtractor()
    elif feature_key == "f":
        fse = FunctionalityStatExtractor()
    else:
        argparser.error("Incorrect feature-key identifier")
    
    rows = fse.get_data(database_file, quantity)

    x = [row['info'].split('.')[-1] for row in rows]
    y = [row['freq'] for row in rows] 
    
    plt.hist(x, weights=y, bins=len(x))
    plt.show()
    
    

if __name__ == '__main__':
    main()