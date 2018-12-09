from sqlalchemy import Column, Integer, String, DateTime
from model.DB import Base


class Property(Base):
    __tablename__ = "properties"
    identifier = Column(String(50), primary_key=True)
    int_val = Column(Integer, nullable=True)
    text_val = Column(String(500), nullable=True)
    date_val = Column(DateTime, nullable=True)

    def __init__(self, identifier, int_val=None, text_val=None, date_val=None):
        self.identifier = identifier
        self.int_val = int_val
        self.text_val = text_val
        self.date_val = date_val
