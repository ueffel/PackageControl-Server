# PackageControl-Server

This a [Flask](http://flask.pocoo.org/) application to host a package repository for [Keypirinha-PackageControl](https://github.com/ueffel/Keypirinha-PackageControl).

## Installation
* Download or clone the repository
* Run `pip install -r requirements.txt`
* Copy or rename `config.py.template` to `config.py`
* Edit `config.py` to configure application key, database storage and repository name
* Configure the wsgi server of your choice to serve `app` from the `packagecontrol.py` file or
  install [cheroot](https://pypi.org/project/Cheroot/) and just run `packagecontrol.py` (deployment
  at http://localhost:9001/packagecontrol/)

## Using the repository
* Open Browser and add packages
* Change your Keypirinha-PackageControl configuration to your repository location (bottom of the
  index page)

## Advanced usage
* Write a new packages source class to support your own way of providing packages
* Inherit from PackageSourceBase and implement `update` and `is_available`
* Look at the other sources for some implementation pointers
* Put it into model\PackageSource\

Example: MyAwesomePackageSource.py
```python
from model.PackageSource.PackageSourceBase import PackageSourceBase


class MyAwesomePackageSource(PackageSourceBase):
    description = "My totally awesome Packagesource"

    def __init__(self, package):
        super().__init__(package)

    def update(self):
        """Fill the attributes of the object by querying the source

        :return True/False if updating was successful
        """
        # Try to set all of the below attributes
        self.package.name = name
        self.package.description = description
        self.package.filename = filename
        self.package.date = date
        self.package.version = version
        self.package.download_url = download_url
        self.package.homepage = homepage
        return True

    def is_available(self):
        """Should be a cheap check if the package source is available to be used when submitting a
        package as validation

        :return True/False if the package source is available
        """
        return True
```
