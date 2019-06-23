import inspect
import asyncio
import json
import requests
import traceback
import model.PackageSource
from flask import Flask, redirect, jsonify, render_template, url_for, request, Response, stream_with_context
from sqlalchemy import or_, and_, not_
from sqlalchemy.orm import defer, load_only
from datetime import datetime, timedelta
from model.DB import db_session, init_db
from model.Package import Package
from model.Property import Property
from config import REPO_NAME, LOGGER, SECRET_KEY, ADMIN_PW
from model.PackageSource import PackageSourceBase
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
                                                 defer(Package.path),
                                                 defer(Package.download_url)).all()
    return render_template("index.html",
                           title="{} ({} packages)".format(REPO_NAME, len(packages)),
                           packages=packages,
                           repo_url=url_for("packages_json", _external=True),
                           ptype_descriptions=package_sources_descriptions)


@app.route("/packages.json")
def packages_json():
    return Response(stream_with_context(packages_json_generate()), 200, mimetype="application/json")


def packages_json_generate():
    yield '{{"name":"{}","packages":['.format(REPO_NAME)

    cached_packages = db_session.query(Package) \
        .filter(Package.last_updated.isnot(None),
                or_(and_(Package.last_update_successful,
                         Package.last_updated >= datetime.utcnow() - timedelta(hours=24)))) \
        .options(load_only(Package.owner,
                           Package.name,
                           Package.description,
                           Package.filename,
                           Package.date,
                           Package.version,
                           Package.download_url,
                           Package.homepage))
    iter_cached_packages = iter(cached_packages)
    package = next(iter_cached_packages, None)
    if package:
        yield json_dump_package(package)
    for package in iter_cached_packages:
        yield "," + json_dump_package(package)

    update_packages = db_session.query(Package) \
        .filter(or_(Package.last_updated.is_(None),
                    and_(Package.last_update_successful,
                         Package.last_updated < datetime.utcnow() - timedelta(hours=24)),
                    and_(not_(Package.last_update_successful),
                         Package.last_updated < datetime.utcnow() - timedelta(hours=4)))) \
        .options(load_only(Package.owner,
                           Package.repo,
                           Package.path,
                           Package.ptype,
                           Package.date))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update_tasks = [asyncio.ensure_future(update_package(package)) for package in update_packages]
    iter_update_tasks = asyncio.as_completed(update_tasks)
    if not package:
        update_task = next(iter_update_tasks, None)
        if update_task:
            updated_package = None
            try:
                updated_package = loop.run_until_complete(update_task)
            except Exception as ex:
                LOGGER.error(ex)
                LOGGER.debug(traceback.format_exc())
            if updated_package:
                yield json_dump_package(updated_package)
    for update_task in iter_update_tasks:
        try:
            updated_package = loop.run_until_complete(update_task)
        except Exception as ex:
            LOGGER.error(ex)
            LOGGER.debug(traceback.format_exc())
            continue
        if updated_package:
            yield "," + json_dump_package(updated_package)
    loop.close()

    if update_tasks:
        last_updated_prop = Property("last_updated", date_val=datetime.utcnow())
        last_updated_prop = db_session.merge(last_updated_prop)
        db_session.commit()
        last_updated = last_updated_prop.date_val
    else:
        last_updated = db_session.query(Property.date_val).filter(Property.identifier == "last_updated").scalar()

    yield '],"last_updated":"{}"}}'.format(last_updated.isoformat() if last_updated else "")


def json_dump_package(package):
    return json.dumps({
        "date": package.date.isoformat(),
        "description": package.description,
        "download_url": package.download_url,
        "filename": package.filename,
        "homepage": package.homepage,
        "name": package.name,
        "owner": package.owner,
        "version": package.version
    }, separators=(',', ':'))


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
                    Package.last_updated <= datetime.utcnow() - timedelta(hours=2))) \
        .options(load_only(Package.owner,
                           Package.repo,
                           Package.path,
                           Package.ptype,
                           Package.date)) \
        .first()
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


def insert_package(owner, repo, ptype, path=None, added=None, commit=True):
    package = Package(owner, repo, ptype, path, added)
    source_type = next((package_source for package_source in package_sources
                        if package_source.__name__ == package.ptype), None)
    if source_type:
        source_type(package)
        db_session.add(package)
        if commit:
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


@app.route("/sync/")
def synchronize():
    packages = db_session.query(Package).options(load_only(Package.owner,
                                                           Package.repo,
                                                           Package.ptype,
                                                           Package.path,
                                                           Package.added)).all()
    packages_serialized = [
        {
            "owner": package.owner,
            "repo": package.repo,
            "ptype": package.ptype,
            "path": package.path,
            "added": package.added.isoformat()
        }
        for package in packages
    ]
    return jsonify(packages_serialized)


@app.route("/sync/start/")
def do_synchronize():
    auth_check = check_auth()
    if auth_check:
        return auth_check

    mirrors = db_session.query(Property) \
        .filter(Property.identifier.like("MIRROR_%")) \
        .options(load_only(Property.identifier, Property.text_val)) \
        .all()

    if not mirrors:
        return Response("No mirrors set up.\n", 500, mimetype="text/plain")

    return Response(stream_with_context(do_synchronize_generate(mirrors)), mimetype="text/plain")


def check_auth():
    if not ADMIN_PW:
        return Response("ADMIN_PW is not configured. No synchronisation possible.\n", 500, mimetype="text/plain")

    auth = request.authorization
    if not auth:
        return Response('Could not verify your access level for that URL.\nYou have to login with proper credentials.',
                        401,
                        {'WWW-Authenticate': 'Basic realm="Login Required"'},
                        mimetype="text/plain")

    if auth.username != "admin" or auth.password != ADMIN_PW:
        return Response("You are not allowed to do that!\n", 403, mimetype="text/plain")

    return None


def do_synchronize_generate(mirrors):
    yield "Starting synchronize...\n"
    packages_added_all = 0

    for mirror in mirrors:
        yield "Synchronizing '{}'\n".format(mirror.text_val)
        try:
            resp = requests.get(mirror.text_val)
            if resp.status_code != 200:
                continue

            packages_mirror = json.loads(resp.content)
            packages = db_session.query(Package).options(load_only(Package.owner,
                                                                   Package.repo,
                                                                   Package.path,
                                                                   Package.ptype)).all()
            packages_added = 0
            for package_mirror in packages_mirror:
                found = False
                for package in packages:
                    if package_mirror["owner"] == package.owner \
                            and package_mirror["ptype"] == package.ptype \
                            and package_mirror["repo"] == package.repo \
                            and package_mirror["path"] == package.path:
                        found = True
                        break
                if not found:
                    LOGGER.info("Synchronize: adding %s", package_mirror)
                    insert_package(package_mirror["owner"],
                                   package_mirror["repo"],
                                   package_mirror["ptype"],
                                   package_mirror["path"],
                                   package_mirror["added"],
                                   commit=False)
                    yield "adding {}\n".format(package_mirror)
                    packages_added += 1
            packages_added_all += packages_added
            yield "Mirror '{}': {} packages added.\n".format(mirror.text_val, packages_added)
        except Exception as ex:
            LOGGER.error(ex)
            error = "{}: {}\n".format(ex, traceback.format_exc())
            LOGGER.debug(error)
            yield error

    if packages_added_all > 0:
        db_session.commit()

    yield "Synchronization successful.\n"


@app.route("/sync/mirrors/")
def sync_mirrors():
    auth_check = check_auth()
    if auth_check:
        return auth_check

    mirrors = db_session.query(Property) \
        .filter(Property.identifier.like("MIRROR_%")) \
        .options(load_only(Property.identifier, Property.text_val)) \
        .all()
    return Response("List of mirrors:\n{}\n".format("\n".join(["{}: {}".format(mirror.identifier, mirror.text_val)
                                                               for mirror in mirrors])),
                    200,
                    mimetype="text/plain")


@app.route("/sync/add_mirror/<path:url>")
def add_mirror(url):
    auth_check = check_auth()
    if auth_check:
        return auth_check

    resp = requests.head(url)
    if resp.status_code != 200:
        return Response("'{}' not available. Status code was {}\n".format(url, resp.status_code),
                        400,
                        mimetype="text/plain")

    mirrors = db_session.query(Property) \
        .filter(Property.identifier.like("MIRROR_%")) \
        .options(load_only(Property.identifier, Property.text_val)) \
        .all()

    duplicate = False
    for mirror in mirrors:
        if mirror.text_val == url:
            duplicate = True
            break

    if duplicate:
        return Response("'{}' is already a mirror.\n".format(url), 200, mimetype="text/plain")

    if mirrors:
        new_mirror_nr = max([int(mirror.identifier[len("MIRROR_"):]) for mirror in mirrors]) + 1
    else:
        new_mirror_nr = 0
    new_mirror = Property("MIRROR_" + str(new_mirror_nr), text_val=url)
    db_session.add(new_mirror)
    db_session.commit()

    return Response("'{}' added as mirror.\n".format(url), 200, mimetype="text/plain")


@app.route("/sync/delete_mirror/<string:identifier>")
def delete_mirror(identifier):
    auth_check = check_auth()
    if auth_check:
        return auth_check

    mirror = db_session.query(Property) \
        .filter(Property.identifier.like("MIRROR_%")) \
        .options(load_only(Property.identifier)) \
        .first()

    if mirror:
        db_session.delete(mirror)
        db_session.commit()
        return Response("Mirror '{}' removed.\n".format(identifier), 200, mimetype="text/plain")
    else:
        return Response("Mirror '{}' not found.\n".format(identifier), 404, mimetype="text/plain")


@app.teardown_appcontext
def shutdown_session(exception=None):
    if exception:
        LOGGER.warning("Shutdown Exception: %s", exception)
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
