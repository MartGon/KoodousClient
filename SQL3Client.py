
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
        
    def execute(self, statement, *args):
        return self.cursor.execute(statement, *args)
        
    def fetchone(self):
        return self.cursor.fetchone()
        
    def commit(self):
        self.conn.commit();
        
    def close(self):
        self.conn.close();
        
class NullSQL3Client(SQL3Client):

    def connect(self, database_file):
        pass
        
    def execute(self, statement,*args):
        pass
        
    def fetchone(self):
        pass
    
    def commit(self):
        pass
    
    def close(self):
        pass