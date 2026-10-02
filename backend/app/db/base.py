from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

'''
DeclarativeBase 是 SQLAlchemy 2.0 的寫法，繼承它的類別可以用 Python class 描述資料表。
Base 本身不做事（pass），它的用途是登記簿：之後所有 class User(Base) 都會登記到 Base.metadata，建表時就靠它知道有哪些表。
'''