# PackageControl-Server

This a [Flask](http://flask.pocoo.org/) application to host a package repository for
[Keypirinha-PackageControl](https://github.com/ueffel/Keypirinha-PackageControl).

## Installation
* Download or clone the repository
* Run `pip install -r requirements.txt`
* Copy or rename `config.py.template` to `config.py`
* Edit `config.py` to configure application key, database storage and repository name
* Configure the wsgi server of your choice to serve `app` from the `packagecontrol.py` file or
  install [cheroot](https://pypi.org/project/Cheroot/) and just run `packagecontrol.py` (deployment
  at http://localhost:9001/packagecontrol/)

## Using the repository
* Open browser and add packages
* Change your Keypirinha-PackageControl configuration to your repository's packages.json location
  (if everything works its in the text field at the bottom of the index page)

## Advanced usage
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
    description = "Just a URL to a Package"  # Description of the package source
    path_required = True                     # determines if the "path" field is displayed in the submit form

    def __init__(self, package):
        """The following attributes are set from the submit from
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
            self.package.version = ""
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
