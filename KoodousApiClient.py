
import requests
import urllib

class KoodousApiClient:
    
    URL = 'https://koodous.com/api/%s%s%s'

    def __init__(self, token):
        self.TOKEN = token
        self.headers = {'Authorization': 'Token %s' % self.TOKEN}
        self.sha256 = ''
        
    def search_koodous_db(self, term, page=1, page_size=25):
        url = self.URL % ('apks', '?search=%s&page=%i&page_size=%i' % (term, page, page_size), "" )
        return requests.get(url=url, headers=self.headers)
        
    def get_info(self, sha256):
        url = self.URL % ('apks/', sha256, '')
        return requests.get(url, headers=self.headers)
        
    def download(self, sha256, dest=None):
        
        url = self.URL % ('apks/', sha256, '/download')
        r = requests.get(url=url, headers=self.headers)
        
        if r.status_code is 200:
            j = r.json()

            with open(dest, "wb") as file:
                response = requests.get(j['download_url'])
                file.write(response.content)

        return r.status_code
        
     