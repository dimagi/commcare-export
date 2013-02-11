import requests

class CommCareHqClient():
    """
    A connection to CommCareHQ for a particular version, domain, and user.
    """

    def __init__(self, url, domain, version='0.3', session=None):
        self.version = version
        self.url = url
        self.domain = domain
        self.__session = session

    @property
    def session(self):
        if self.__session == None:
            self.__session = requests.Session()
        return self.__session

    @property
    def api_url(self):
        return '%s/a/%s/api/v%s' % (self.url, self.domain, self.version)

    def authenticated(self, username=None, password=None):
        """
        Returns a freshly authenticated CommCareHqClient with a new session.
        This is safe to call many times and each of the resulting clients
        remain independent, so you can log in with zero, one, or many users.
        """

        login_url = '%s/accounts/login/' % self.url
        session = requests.Session()
        
        # Pick up things like CSRF cookies and form fields by doing a GET first
        response = session.get(login_url)
        if response.status_code != 200:
            raise Exception('Failed to connect to authentication page (%s): %s' % (response.status_code, response.text))

        response = session.post(login_url, data = {'username': username, 
                                                   'password': password, 
                                                   'csrfmiddlewaretoken': response.cookies['csrftoken']})
        if response.status_code != 200:
            raise Exception('Authentication failed (%s): %s' % (response.status_code, response.text))
        
        return CommCareHqClient(url = self.url, domain = self.domain, version = self.version, session = session)

    def get(self, resource):
        """
        Gets the named resource.

        Currently a bit of a vulnerable stub that works
        for this particular use case in the hands of a trusted user; would likely
        want this to work like (or via) slumber.
        """
        resource_url = '%s/%s/' % (self.api_url, resource)
        response = self.session.get(resource_url)

        if response.status_code != 200:
            raise Exception('GET %s failed (%s): %s' % (resource_url, response.status_code, response.text))
        else:
            return response.json()
            
