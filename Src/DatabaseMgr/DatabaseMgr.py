from DatabaseMgr.SQL3Client import *

import os

class DBConnectionException(Exception):
    pass

class DatabaseManager:

    dbclient = None

    def connect_db(self, database_file):
        
        # Connect to database
        self.dbclient = SQL3Client()
        exists = os.path.exists(database_file)
        
        # Init databse
        if not exists:
            raise DBConnectionException("Warning: Database doesn't exist, initializing...")
            
        self.dbclient.connect(database_file)
        
    def disconnect_db(self):
        
        self.dbclient.commit()
        self.dbclient.close()