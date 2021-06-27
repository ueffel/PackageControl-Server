from model.PackageSource.PackageSourceBase import PackageSourceBase
from config import LOGGER, GITHUB_BASIC_AUTH_USER, GITHUB_BASIC_AUTH_TOKEN
from requests.auth import HTTPBasicAuth
import requests
import json
import dateutil.parser
import traceback
import urllib


class Github(PackageSourceBase):
    description = "An entire repository on github.com dedicated to the package"
    long_description = "(recommended) A entire github repository to the package. It should have a release" \
                       " (not pre-release) in its releases section which has a ready-to-use *.keypirinha-package file" \
                       " as an asset. The download URL will point to the newest release by date that has such an" \
                       " asset. The github user and the repository is needed."
    path_required = False

    def __init__(self, package):
        super().__init__(package)
        self.package.name = self.package.repo
        self.package.homepage = "https://github.com/{}/{}".format(self.package.owner, self.package.repo)

    def update(self):
        try:
            api_url = "https://api.github.com/graphql"
            query_str = """{
  repository(owner: "%s", name: "%s") {
    releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        releaseAssets(first: 10) {
          nodes {
            name
            downloadUrl
            downloadCount
          }
        }
        tagName
        isPrerelease
        isDraft
        publishedAt
      }
    }
    description
    stargazers {
      totalCount
    }
  }
}""" % (self.package.owner, self.package.repo)

            query = {
                "query": query_str,
                "variables": None,
            }

            auth = HTTPBasicAuth(GITHUB_BASIC_AUTH_USER, GITHUB_BASIC_AUTH_TOKEN) \
                if GITHUB_BASIC_AUTH_USER and GITHUB_BASIC_AUTH_TOKEN else None

            repo_info = json.loads(self.do_post_request(api_url, json=query, auth=auth))
            self.package.description = repo_info["data"]["repository"]["description"] if repo_info["data"]["repository"]["description"] else "no description"
            self.package.stars = repo_info["data"]["repository"]["stargazers"]["totalCount"]

            release_found = False
            releases = repo_info["data"]["repository"]["releases"]["nodes"]
            for release in releases:
                release_date = dateutil.parser.parse(release["publishedAt"], ignoretz=True)
                if release["isDraft"] or release["isPrerelease"] or self.package.date is not None and self.package.date > release_date:
                    continue
                for asset in release["releaseAssets"]["nodes"]:
                    if asset["name"].endswith(".keypirinha-package"):
                        self.package.date = release_date
                        self.package.version = release["tagName"]
                        self.package.download_url = asset["downloadUrl"]
                        self.package.download_count = asset["downloadCount"]
                        self.package.filename = asset["name"]
                        release_found = True
                        break

            if not release_found:
                LOGGER.error("No release found in repo: %s: %s", self.package.owner, self.package.repo)
                return False
        except Exception as ex:
            LOGGER.error(ex)
            LOGGER.debug(traceback.format_exc())
            return False

        return True

    def is_available(self):
        url = "https://github.com/{}/{}".format(self.package.owner, self.package.repo)
        req = requests.head(url)
        if req.status_code == 200:
            return True
        else:
            return False
