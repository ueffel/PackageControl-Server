from model.PackageSource.PackageSourceBase import PackageSourceBase
from config import LOGGER, GITHUB_BASIC_AUTH_USER, GITHUB_BASIC_AUTH_TOKEN
from datetime import timezone
from requests.auth import HTTPBasicAuth
import requests
import json
import dateutil.parser
import traceback
import urllib


class Gitea(PackageSourceBase):
    name = "Gitea/Forgejo"
    description = "An entire repository on a gitea or forgejo instance dedicated to the package."
    long_description = "An entire repository on a gitea or forgejo (e.g. codeberg.org) instance dedicated to the package. " \
                       "It should have a release (not pre-release) in its releases section which has a ready-to-use " \
                       "*.keypirinha-package file as an asset. The download URL will point to the newest release by date " \
                       "that has such an asset. The github user and the repository is needed."
    path_required = True

    def __init__(self, package):
        super().__init__(package)
        repo_url = urllib.parse.urlparse(self.package.path)
        path_parts = repo_url.path.split("/", 4)
        if len(path_parts) >= 3:
            self.package.owner = path_parts[1]
            self.package.repo = path_parts[2]
            repo_url = repo_url._replace(path=urllib.parse.urljoin("/api/v1/repos/", self.package.owner+"/"+self.package.repo))
            self._api_url = repo_url.geturl()
            self.package.name = self.package.repo
        self.package.homepage = self.package.path

    def update(self):
        try:
            repo_info = json.loads(self.do_get_request(self._api_url))
            self.package.description = repo_info["description"]
            self.package.stars = repo_info["stars_count"]

            request_url = "{}/releases".format(self._api_url)
            releases = json.loads(self.do_get_request(request_url))
            release_found = False
            for release in releases:
                release_date = dateutil.parser.parse(release["published_at"])
                release_date = release_date.astimezone(timezone.utc).replace(tzinfo=None)
                if release["draft"] or release["prerelease"] or self.package.date is not None and self.package.date > release_date:
                    continue
                self.package.date = release_date
                self.package.version = release["tag_name"]
                for asset in release["assets"]:
                    if asset["name"].endswith(".keypirinha-package"):
                        self.package.download_url = asset["browser_download_url"]
                        self.package.filename = asset["name"]
                        self.package.download_count = asset["download_count"]
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
        req = requests.get(self._api_url)
        return req.status_code == 200
