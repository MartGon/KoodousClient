
import requests
import urllib

class DownloadException(Exception):
    pass

class KoodousApiClient:
    
    URL = 'https://koodous.com/api/%s%s%s'
    TOKENS = []
    TOKEN_INDEX = 0

    def __init__(self, tokens):
        
        if not isinstance(tokens, list):
            if tokens is not None:
                TOKENS.append(tokens)
            
    
        self.TOKENS = tokens
        self.headers = {'Authorization': 'Token %s' % self.TOKENS[self.TOKEN_INDEX]}
        
    def search_koodous_db(self, term, quantity=25):
        url = self.URL % ('apks', '?search=%s' % (term), "" )
        resp = requests.get(url=url, headers=self.headers).json()
        
        found = resp['results']
        while len(found) < quantity:
            next = resp['next']
            resp = requests.get(url=next, headers=self.headers).json()
            
            to_append = min(len(resp['results']), quantity - len(found))
            found.extend(resp['results'][:to_append])
            
        if len(found) > quantity:
            found = found[:quantity]
        
        return found
        
    def get_info(self, sha256):
        url = self.URL % ('apks/', sha256, '')
        return requests.get(url, headers=self.headers)
        
    def download(self, sha256, dest=None, failing_servers=[]):
        
        url = self.URL % ('apks/', sha256, '/download')
        r = requests.get(url=url, headers=self.headers)
        
        # Everythin is fine
        if r.status_code is 200:
            j = r.json()

            download_url = j['download_url']
            
            if self.__is_failing_server(download_url, failing_servers):
                print("Download from failing server avoided: %s" % download_url)
                return 404, download_url
            
            with open(dest, "wb") as file:
                response = requests.get(j['download_url'], headers=self.headers)
                file.write(response.content)
        
        # Max download rate reached
        elif r.status_code == 429:
            print("Error: Max download rate reached for token %s" % self.TOKENS[self.TOKEN_INDEX])
            
            # Try to change token and download again
            self.TOKEN_INDEX = self.TOKEN_INDEX + 1
            
            # Check if there are more tokens left
            if self.TOKEN_INDEX >= len(self.TOKENS):
                print("Error: No more tokens left to use today")
                raise DownloadException()
            else:
                # Change header
                self.headers = {'Authorization': 'Token %s' % self.TOKENS[self.TOKEN_INDEX]}
                
                # Try again
                return self.download(sha256, dest, failing_servers)
        else:
            print("Something is wrong")

        return r.status_code, download_url
        
    def __is_failing_server(self, download_url, failing_servers):
        
        for failing_server in failing_servers:
            if failing_server in download_url:
                return True
                
        return False