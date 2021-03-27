# PackageControl-Server

This a [Flask](http://flask.pocoo.org/) application to host a package repository for
[Keypirinha-PackageControl](https://github.com/ueffel/Keypirinha-PackageControl).

## Requirements

* Python >= 3.5
* pip (to install the needed packages)
* wsgi server to serve the app

## Installation

* Download or clone the repository
* Run `pip install -r requirements.txt`
* Copy or rename `config.py.template` to `config.py`
* Edit `config.py` to configure application key, database storage and repository name (optionally
  github basic auth to get around API limits)
* Configure the wsgi server of your choice to serve `app` from the `packagecontrol.py` file or
  install [cheroot](https://pypi.org/project/Cheroot/) and just run `packagecontrol.py` (deployment
  at <http://localhost:9001/packagecontrol/>)

Example configuration for [uwsgi](http://projects.unbit.it/uwsgi) with [nginx](https://nginx.org/):

packagecontrol.ini

```ini
[uwsgi]
plugin = http,python3
pythonpath = /usr/local/lib/python3.5/dist-packages
chdir = /var/www/packagecontrol
mount = /packagecontrol=/var/www/packagecontrol/packagecontrol.py
callable = app
manage-script-name = true
```

nginx conf snippet:

```nginx
location /packagecontrol {
    try_files does_not_exist @packagecontrol;
}

location /packagecontrol/static/ {
    root /var/www;
    try_files $uri @packagecontrol;
}

location @packagecontrol {
    include uwsgi_params;
    uwsgi_pass unix:/var/run/uwsgi/app/packagecontrol/socket;
    uwsgi_param SCRIPT_NAME /packagecontrol;
    uwsgi_modifier1 30;
}
```

## Using the repository

* Open browser and add packages
* Change your Keypirinha-PackageControl configuration to your repository's packages.json location
  (if everything works its in the text field at the bottom of the index page)

## Advanced usage

* Use the `/sync/`, `/sync/start/`, `/sync/mirrors/`, `/sync/add_mirror/<url>` and
  `/sync/delete_mirror/<key>` end points to synchronize with another repository (Secured with basic
  authentication with username "admin" and password configurable with `ADMIN_PW` setting)
  * `/sync/` is the endpoint for mirrors to get the all packages (not secured)
  * `/sync/mirrors/` lists all configured mirrors in the format `key: url`
  * `/sync/add_mirror?url=<url>` checks and adds `url` as a mirror (should be the `/sync/` endpoint of
    another repository, e.g. <https://ue.spdns.de/packagecontrol/sync/>)

    ```http://localhost:9001/packagecontrol/sync/add_mirror/?url=https://ue.spdns.de/packagecontrol/sync```

  * `/sync/start/` starts the synchronisation process
  * `/sync/delete_mirror/<key>` removes a mirror (`key` from `/sync/mirrors/` endpoint, e.g.
    MIRROR_0)
* Write a new packages source class to support your own way of providing packages
* Inherit from PackageSourceBase and implement `update` and `is_available`
* Look at the other sources for some implementation pointers
* Put it into model\PackageSource\

Example: WebFile.py

```python
import requests
import os.path
import dateutil.parser
from model.PackageSource.PackageSourceBase import PackageSourceBase
from config import LOGGER


class WebFile(PackageSourceBase):
    # Description of the package source
    description = "Just a URL to a Package"
    # Long description to be shown in the submission form
    long_description = "The download URL will point directly to submitted path and the date will be the last-modified" \
                       " HTTP header if its provided by the source. The author, name and complete URL is needed."
    # Determines if the "path" field is displayed in the submit form
    path_required = True

    def __init__(self, package):
        """The following attributes are set from the submit form
        self.package.type
        self.package.owner
        self.package.repo
        self.package.path

        Set at least name and homepage in the constructor to display on the index page if no update
        call has been done yet
        """
        super().__init__(package)
        self.package.name = self.package.repo      # name display on the index page and in the first line in keypirinha
        self.package.homepage = self.package.path  # url to webpage for more information on the package

    def update(self):
        """Fill the attributes of the object by querying the its source

        :return True/False if updating was successful
        """
        # Try to set all of the below attributes during update
        # self.package.description    # description of the package (second line in keypirinha)
        # self.package.filename       # filename which is used to save the package file when installing
        # self.package.date           # date that is used to determine if the package needs an update
        # self.package.version        # version string of the package
        # self.package.download_url   # url where the package can be downloaded

        try:
            resp = requests.head(self.package.path)
            if "last-modified" in resp.headers:
                date_header = resp.headers["last-modified"]
                date = dateutil.parser.parse(date_header)
            else:
                date = None
            self.package.description = "Keypirinha package from: " + self.package.path
            self.package.filename = os.path.basename(self.package.path)
            self.package.date = date if date else self.package.added
            self.package.version = "1.0.0+" + self.package.date.strftime("%Y%m%d%H%M")
            self.package.download_url = self.package.path
            return True
        except Exception as exc:
            LOGGER.error(exc)
            return False

    def is_available(self):
        """Should be a cheap check if the package source is available to be used when submitting a
        package as validation

        :return True/False if the package source is available
        """
        return requests.head(self.package.path).status_code == 200
```
