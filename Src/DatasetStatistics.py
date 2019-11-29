
from DatabaseMgr.SQL3Client import *

import matplotlib.pyplot as plt
import argparse

def main():

    # Config argument parser
    argparser = argparse.ArgumentParser(description='Koodous dataset downloader')
    argparser.add_argument('--database-file', '-dbf', help = 'SQL3 database file location', required=True)
    argparser.add_argument('--quantity', '-q', help = 'Amount of values to show in the histogram', default = 10, type=int)
    
    # Parser arguments
    args = argparser.parse_args()
    database_file = args.database_file
    quantity = args.quantity
    
    # Connect to database
    dbclient = SQL3Client()
    dbclient.connect(database_file)
    
    # Get data
    dbclient.execute('''select id, info, count(permission) as freq from apk_permissions INNER JOIN permissions ON apk_permissions.permission = permissions.id group by permission ORDER BY count(permission) DESC LIMIT :quantity''', {'quantity':quantity})
    rows = dbclient.fetchall()
    
    x = [row['info'].split('.')[-1] for row in rows]
    y = [row['freq'] for row in rows] 
    
    plt.hist(x, weights=y, bins=len(x))
    plt.show()
    
    

if __name__ == '__main__':
    main()