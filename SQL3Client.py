
import sqlite3

class SQL3Client:

    conn = None
    cursor = None
    database_file = None

    def __init__(self):
        pass
    
    def connect(self, database_file):
        self.conn = sqlite3.connect(database_file)
        self.cursor = self.conn.cursor()
        
    def execute(statement, *args):
        self.cursor.execute(statement, list(args))
        
    def commit(self):
        self.conn.commit();
        
    def close(self):
        sefl.conn.close();
        
class NullSQL3Client(SQL3Client):

    def connect(self, database_file):
        pass
        
    def execute(statement,*args):
        pass
    
    def commit(self):
        pass
    
    def close(self):
        pass