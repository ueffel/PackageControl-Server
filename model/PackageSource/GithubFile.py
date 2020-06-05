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
                                                                                 self.package.path.lstrip("/"))

    def update(self):
        try:
            api_url = "https://api.github.com/graphql"
            query_str = """{
  repository(owner: "%s", name: "%s") {
    object(expression: "master") {
      ... on Commit {
        history(first: 1, path: "%s") {
          nodes {
            committedDate
            oid
          }
        }
      }
    }
  }
}""" % (self.package.owner, self.package.repo, self.package.path.lstrip("/"))

            query = {
                "query": query_str,
                "variables": None,
            }

            auth = HTTPBasicAuth(GITHUB_BASIC_AUTH_USER, GITHUB_BASIC_AUTH_TOKEN) \
                if GITHUB_BASIC_AUTH_USER and GITHUB_BASIC_AUTH_TOKEN else None

            repo_info = json.loads(self.do_post_request(api_url, json=query, auth=auth))

            if len(repo_info["data"]["repository"]["object"]["history"]["nodes"]) == 0:
                raise ValueError("no commits found")

            commit = repo_info["data"]["repository"]["object"]["history"]["nodes"][0]

            self.package.description = "no description"
            self.package.date = dateutil.parser.parse(commit["committedDate"], ignoretz=True)
            self.package.download_url = "https://github.com/{}/{}/raw/{}/{}".format(
                self.package.owner,
                self.package.repo,
                commit["oid"],
                self.package.path.lstrip("/"))
            self.package.filename = os.path.basename(self.package.path)
            self.package.version = "1.0.0+" + commit["oid"][:7]
            return True
        except Exception as ex:
            LOGGER.error(ex)
            LOGGER.debug(traceback.format_exc())
            return False

    def is_available(self):
        url = "https://github.com/{}/{}/blob/master/{}".format(self.package.owner,
                                                               self.package.repo,
                                                               self.package.path.lstrip("/"))
        req = requests.head(url)
        if req.status_code == 200:
            return True
        else:
            return False
