import requests
import urllib


class PackageSourceBase(object):
    def __init__(self, package):
        self.package = package

    def update(self):
        """Fill the attributes of the object by querying the source

        :return True/False if updating was successful
        """
        raise NotImplementedError

    def is_available(self):
        """Should be a cheap check if the package source is available to be used when submitting a package as validation

        :return True/False if the package source is available
        """
        raise NotImplementedError

    @staticmethod
    def do_get_request(url, parameters=None, auth=None):
        req = requests.get(url, params=parameters, proxies=urllib.request.getproxies(), auth=auth)
        if req.status_code == 200:
            return req.text
        else:
            raise requests.HTTPError("Request to '{}' failed: {} {}".format(url, req.status_code, req.text))
