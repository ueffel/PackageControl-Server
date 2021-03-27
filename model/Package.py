from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Boolean, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from model.DB import Base


class Package(Base):
    __tablename__ = "packages"
    pid = Column(Integer, primary_key=True, autoincrement=True)
    owner = Column(String(100), nullable=False)
    repo = Column(String(100), nullable=False)
    ptype = Column(String(100), nullable=False)
    path = Column(String(100), nullable=True)
    added = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_updated = Column(DateTime, nullable=True)
    last_update_successful = Column(Boolean, nullable=False, default=False)
    name = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    filename = Column(String(255), nullable=True)
    date = Column(DateTime, nullable=True)
    version = Column(String(50), nullable=True)
    download_url = Column(String(1000), nullable=True)
    download_count = Column(Integer, nullable=True)
    homepage = Column(String(1000), nullable=True)
    stars = Column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("owner", "repo", "ptype", "path"),)

    def __init__(self, owner=None, repo=None, ptype=None, path=None, added=None, last_updated=None,
                 last_update_successful=None, name=None, description=None, filename=None, date=None, version=None,
                 download_url=None, download_count=None, homepage=None):
        self.owner = owner
        self.repo = repo
        self.ptype = ptype
        self.path = path
        self.added = added
        self.last_updated = last_updated
        self.last_update_successful = last_update_successful
        self.name = name
        self.description = description
        self.filename = filename
        self.date = date
        self.version = version
        self.download_url = download_url
        self.download_count = download_count
        self.homepage = homepage

    @hybrid_property
    def updatable(self):
        return self.last_updated is None or self.last_updated <= datetime.utcnow() - timedelta(hours=4)
