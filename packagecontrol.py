import inspect
import asyncio
import dateutil.parser
import feedgenerator
import json
import requests
import pytz
import traceback
import model.PackageSource
from flask import Flask, redirect, jsonify, render_template, url_for, request, Response, stream_with_context
from sqlalchemy import or_, and_, not_, func, desc, asc
from sqlalchemy.orm import defer, load_only
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from wsgiref.handlers import format_date_time
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
                                                 defer(Package.filename),
                                                 defer(Package.path)).all()
    for package in packages:
        if package.name.startswith("Keypirinha-"):
            package.name = package.name[len("Keypirinha-"):]
        if package.name.startswith("keypirinha-"):
            package.name = package.name[len("keypirinha-"):]
        if package.name.startswith("Plugin-"):
            package.name = package.name[len("Plugin-"):]
    return render_template("index.html",
                           title=REPO_NAME,
                           packages=packages,
                           repo_url=url_for("packages_json", _external=True),
                           ptype_descriptions=package_sources_descriptions)


@app.route("/packages.json")
def packages_json():
    update_needed = db_session.query(func.count(Package.pid)) \
        .filter(or_(Package.last_updated.is_(None),
                    and_(Package.last_update_successful,
                         Package.last_updated < datetime.utcnow() - timedelta(hours=24)),
                    and_(not_(Package.last_update_successful),
                         Package.last_updated < datetime.utcnow() - timedelta(hours=4)))).scalar() > 0

    return Response(stream_with_context(packages_json_generate()),
                    mimetype="application/json",
                    headers={"X-Accel-Buffering": "no" if update_needed else "yes"})


def packages_json_generate():
    yield '{{"name":"{}","packages":['.format(REPO_NAME)

    cached_packages = db_session.query(Package) \
        .filter(Package.last_updated.isnot(None),
                Package.last_update_successful,
                Package.last_updated >= datetime.utcnow() - timedelta(hours=24)) \
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
                           title=REPO_NAME,
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

    return Response(stream_with_context(do_synchronize_generate(mirrors)),
                    mimetype="text/plain",
                    headers={"X-Accel-Buffering": "no"})


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

    for mirror in mirrors:
        yield "Synchronizing '{}'\n".format(mirror.text_val)
        try:
            resp = requests.get(mirror.text_val)
            if resp.status_code != 200:
                yield "Errornous http status code: {}. Skipping this mirror.\n".format(resp.status_code)
                continue

            packages_mirror = json.loads(resp.content)
            packages = db_session.query(Package).options(load_only(Package.owner,
                                                                   Package.repo,
                                                                   Package.path,
                                                                   Package.ptype)).all()
            packages_added = 0
            for package_mirror in packages_mirror:
                found = False
                if "path" not in package_mirror:
                    package_mirror["path"] = None
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
                                   dateutil.parser.parse(package_mirror["added"]),
                                   commit=False)
                    yield "adding {}\n".format(package_mirror)
                    packages_added += 1

            if packages_added > 0:
                try:
                    db_session.commit()
                except Exception as ex:
                    db_session.rollback()
                    LOGGER.error(ex)
                    LOGGER.debug("{}: {}\n".format(ex, traceback.format_exc()))
                    yield "{}\n".format(ex)
            else:
                db_session.rollback()
            yield "Mirror '{}': {} packages added.\n".format(mirror.text_val, packages_added)
        except Exception as ex:
            LOGGER.error(ex)
            error = "{}: {}\n".format(ex, traceback.format_exc())
            LOGGER.debug(error)
            yield error

    yield "Synchronization done.\n"


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


@app.route("/sync/add_mirror/")
def add_mirror():
    auth_check = check_auth()
    if auth_check:
        return auth_check

    url = request.args.get("url")
    if not url:
        return Response("url is empty, try '{}?url=http://url/'".format(request.url_root + request.path.lstrip("/")),
                        400,
                        mimetype="text/plain")

    try:
        resp = requests.head(url)
        if resp.status_code != 200:
            return Response("'{}' not available. Status code was {}\n".format(url, resp.status_code),
                            400,
                            mimetype="text/plain")
    except Exception as ex:
        return Response("Error occured while checking url: {}".format(ex), 400, mimetype="text/plain")

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


def get_feed_packages():
    return (
        db_session.query(Package)
        .order_by(desc(Package.added), asc(Package.name), asc(Package.owner))
        .options(
            load_only(
                Package.owner,
                Package.name,
                Package.homepage,
                Package.description,
                Package.added,
            )
        )
        .all()
    )

def add_feed_items(feed, packages):
    for package in packages:
        if package.name.startswith("Keypirinha-"):
            package.name = package.name[len("Keypirinha-"):]
        if package.name.startswith("keypirinha-"):
            package.name = package.name[len("keypirinha-"):]
        if package.name.startswith("Plugin-"):
            package.name = package.name[len("Plugin-"):]
        feed.add_item(
            title=package.name,
            author_name=package.owner,
            description=package.description,
            link=package.homepage,
            unique_id=package.homepage,
            pubdate=package.added
        )

def check_if_modified_since():
    if "If-Modified-Since" not in request.headers:
        return False
    ims = request.headers["If-Modified-Since"]
    t = parsedate_to_datetime(ims)
    if not t:
        return False

    max = db_session.query(Package).order_by(desc(Package.added)).limit(1).first()
    if not max:
        return False

    return t >= max.added.replace(tzinfo=pytz.utc)


@app.route("/rss")
def rss_feed():
    if check_if_modified_since():
        return Response(status=304)

    packages = get_feed_packages()
    created = packages[0].added if packages else datetime.utcnow()
    url = url_for("rss_feed", _external=True)
    feed = feedgenerator.Rss201rev2Feed(
        title="Keypirinha-Packagecontrol: New packages",
        link=url,
        description="New packages added to keypirinha packagecontrol",
        pubdate=created,
    )
    add_feed_items(feed, packages)

    return Response(feed.writeString("utf-8"),
                    mimetype=feed.mime_type,
                    headers={"Last-Modified": format_date_time(created.replace(tzinfo=pytz.utc).timestamp())})

@app.route("/atom")
def atom_feed():
    if check_if_modified_since():
        return Response(status=304)

    packages = get_feed_packages()
    created = packages[0].added if packages else datetime.utcnow()
    feed = feedgenerator.Atom1Feed(
        title="Keypirinha-Packagecontrol: New packages",
        link=url_for("index", _external=True),
        feed_url=url_for("atom_feed", _external=True),
        description="New packages added to keypirinha packagecontrol",
        subtitle="New packages added to keypirinha packagecontrol",
        pubdate=created,
    )
    add_feed_items(feed, packages)

    return Response(feed.writeString("utf-8"),
                    mimetype=feed.mime_type,
                    headers={"Last-Modified": format_date_time(created.replace(tzinfo=pytz.utc).timestamp())})

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
