import inspect
import asyncio
import traceback
import model.PackageSource
from flask import Flask, redirect, jsonify, render_template, url_for, request
from sqlalchemy import or_, and_
from sqlalchemy.orm import defer
from datetime import datetime, timedelta
from model.DB import db_session, init_db
from model.Package import Package
from model.Property import Property
from config import REPO_NAME, LOGGER, SECRET_KEY
from model.PackageSource import *


def get_package_sources():
    for ptype in dir(model.PackageSource):
        mod = getattr(model.PackageSource, ptype)
        if not hasattr(mod, ptype):
            continue
        source = getattr(mod, ptype)

        if source and inspect.isclass(source) \
                and issubclass(source, PackageSourceBase.PackageSourceBase) \
                and source != PackageSourceBase.PackageSourceBase:
            package_sources.append(source)
    package_sources_descriptions.update(
        {package_type.__name__: package_type.description for package_type in package_sources})
    package_sources_long_descriptions.update(
        {package_type.__name__: package_type.long_description for package_type in package_sources})


LOGGER.debug("collecting packages sources")
package_sources = []
package_sources_descriptions = {}
package_sources_long_descriptions = {}
get_package_sources()
LOGGER.debug("creating app")
app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.config["package_sources"] = package_sources
app.config["package_sources_descriptions"] = package_sources_descriptions
app.config["package_sources_long_descriptions"] = package_sources_long_descriptions
app.secret_key = SECRET_KEY
LOGGER.debug("initializing db")
init_db()


@app.route("/")
def index():
    packages = db_session.query(Package).options(defer(Package.repo),
                                                 defer(Package.description),
                                                 defer(Package.filename),
                                                 defer(Package.date),
                                                 defer(Package.version),
                                                 defer(Package.download_url)).all()
    return render_template("index.html",
                           title="{} ({} packages)".format(REPO_NAME, len(packages)),
                           packages=packages,
                           repo_url=url_for("packages_json", _external=True),
                           ptype_descriptions=package_sources_descriptions)


@app.route("/packages.json")
def packages_json():
    all_packages = []
    cached_packages = db_session.query(Package) \
        .filter(Package.last_updated.isnot(None),
                or_(and_(Package.last_update_successful.is_(True),
                         Package.last_updated >= datetime.utcnow() - timedelta(hours=24))))
    all_packages.extend(cached_packages.all())

    update_packages = db_session.query(Package) \
        .filter(or_(Package.last_updated.is_(None),
                    and_(Package.last_update_successful.is_(True),
                         Package.last_updated < datetime.utcnow() - timedelta(hours=24)),
                    and_(Package.last_update_successful.is_(False),
                         Package.last_updated < datetime.utcnow() - timedelta(hours=4))))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update_tasks = [asyncio.ensure_future(update_package(package)) for package in update_packages]
    update = asyncio.gather(*update_tasks, return_exceptions=True)
    loop.run_until_complete(update)
    loop.close()

    for update_task in update_tasks:
        exc = update_task.exception()
        if exc:
            LOGGER.error(exc)
            LOGGER.debug("".join(traceback.format_exception(exc.__class__, exc, exc.__traceback__)))
            continue
        updated_package = update_task.result()
        if updated_package:
            all_packages.append(updated_package)

    if update_tasks:
        last_updated_prop = Property("last_updated", date_val=datetime.utcnow())
        last_updated_prop = db_session.merge(last_updated_prop)
        db_session.commit()
        last_updated = last_updated_prop.date_val
    else:
        last_updated = db_session.query(Property.date_val).filter(Property.identifier == "last_updated").scalar()

    packages_serialized = [
        {
            "download_url": package.download_url,
            "name": package.name,
            "filename": package.filename,
            "date": package.date.isoformat(),
            "description": package.description,
            "version": package.version,
            "owner": package.owner,
            "homepage": package.homepage
        }
        for package in all_packages
    ]

    return jsonify(name=REPO_NAME,
                   last_updated=last_updated.isoformat() if last_updated else "",
                   packages=packages_serialized)


@app.route("/new_package", methods=["GET", "POST"])
def new_package():
    from form.SubmitPackageForm import SubmitPackageForm
    form = SubmitPackageForm()

    required_if_fields = form.required_if_fields()

    if request.method == "POST" and form.validate():
        insert_package(form.owner.data, form.repo.data, form.type.data, form.path.data if form.path.data else None)
        return redirect(url_for("index"))

    return render_template("new_package.html",
                           title="Submit a new package to {}".format(REPO_NAME),
                           form=form,
                           required_if_fields=required_if_fields)


@app.route("/update_package/<int:package_id>")
def update_package_by_id(package_id):
    package = db_session.query(Package) \
        .filter(Package.pid == package_id,
                or_(Package.last_updated.is_(None),
                    Package.last_updated <= datetime.utcnow() - timedelta(hours=2))).first()
    if package:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(asyncio.ensure_future(update_package(package)))
            last_updated_prop = Property("last_updated", date_val=datetime.utcnow())
            db_session.merge(last_updated_prop)
            db_session.commit()
        except Exception as ex:
            LOGGER.error(ex)
            LOGGER.debug(traceback.format_exc())
        finally:
            loop.close()

    return redirect(url_for("index"))


def insert_package(owner, repo, ptype, path=None):
    package = Package(owner, repo, ptype, path)
    source_type = next((package_source for package_source in package_sources
                        if package_source.__name__ == package.ptype), None)
    if source_type:
        source_type(package)
        db_session.add(package)
        db_session.commit()


async def update_package(package):
    source_type = next((package_source for package_source in package_sources
                        if package_source.__name__ == package.ptype), None)
    if not source_type:
        return None

    source = source_type(package)
    package.last_update_successful = await asyncio.get_event_loop().run_in_executor(None, source.update)
    package.last_updated = datetime.utcnow()
    return package if package.last_update_successful else None


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


if __name__ == "__main__":
    redirect_app = Flask("redirect")

    @redirect_app.route("/")
    def default():
        return redirect("/packagecontrol/", code=301)

    from cheroot import wsgi
    d = wsgi.PathInfoDispatcher({"/": redirect_app, "/packagecontrol": app})
    server = wsgi.Server(("::", 9001), d)
    server.start()
