from model.PackageSource.PackageSourceBase import PackageSourceBase
from requests.auth import HTTPBasicAuth
from config import LOGGER, GITHUB_BASIC_AUTH_USER, GITHUB_BASIC_AUTH_TOKEN
import requests
import json
import dateutil.parser
import traceback
import os.path


class GithubFile(PackageSourceBase):
    description = "Not a dedicated repository for the package, just a file within collective repository"
    long_description = "A github repository where the *.keypirinha-package file is committed directly into it." \
                       " The download URL will point to the most recent commit of this file. The github user, the" \
                       " repository and a relative path to the file is needed."
    path_required = True

    def __init__(self, package):
        super().__init__(package)
        self.package.name = os.path.splitext(os.path.basename(self.package.path))[0]
        self.package.homepage = "https://github.com/{}/{}/tree/master/{}".format(self.package.owner,
                                                                                 self.package.repo,
                                                                                 self.package.path)

    def update(self):
        try:
            api_url = "https://api.github.com/repos/{}/{}".format(self.package.owner, self.package.repo)
            request_url = "{}/commits".format(api_url)
            auth = HTTPBasicAuth(GITHUB_BASIC_AUTH_USER, GITHUB_BASIC_AUTH_TOKEN) \
                if GITHUB_BASIC_AUTH_USER and GITHUB_BASIC_AUTH_TOKEN else None
            commit_json = json.loads(self.do_get_request(request_url, {'path': self.package.path}, auth=auth))
            latest_commit = max(commit_json,
                                key=lambda commit: dateutil.parser.parse(commit['commit']['committer']['date'],
                                                                         ignoretz=True))
            self.package.date = dateutil.parser.parse(latest_commit['commit']['committer']['date'], ignoretz=True)

            request_url2 = "{}/contents/{}".format(api_url, self.package.path)
            file_json = json.loads(self.do_get_request(request_url2, {'ref': latest_commit['sha']}, auth=auth))
            self.package.download_url = file_json['download_url']
            self.package.filename = file_json['name']
            return True
        except Exception as ex:
            LOGGER.error(ex, traceback.format_exc())
            return False

    def is_available(self):
        url = "https://github.com/{}/{}/blob/master/{}".format(self.package.owner, self.package.repo, self.package.path)
        req = requests.head(url)
        if req.status_code == 200:
            return True
        else:
            return False
