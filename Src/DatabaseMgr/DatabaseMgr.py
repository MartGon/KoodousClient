from DatabaseMgr.SQL3Client import *

import os

class DBConnectionException(Exception):
    pass

class DatabaseManager:

    dbclient = None
    database_file = None

    def connect_db(self, database_file):

        # Connect to database
        self.dbclient = SQL3Client()
        exists = os.path.exists(database_file)
        
        # Init databse
        if not exists:
            raise DBConnectionException("Warning: Database doesn't exist, initializing...")
            
        self.dbclient.connect(database_file)

        # Update file
        self.database_file = database_file

        print("Info: Connecting to DB %s" % database_file)

    def search_db(self, search_param, *args):
            
        if self.dbclient is None:
            raise DBConnectionException("Not Connected to DB. Cannot search db!")    
            
        self.dbclient.execute(search_param, *args)
        return self.dbclient.fetchall()
        
    def disconnect_db(self):
        print("Info: Disconnecting from DB")
        self.dbclient.commit()
        self.dbclient.close()
        self.dbclient = None
        self.database_file = None