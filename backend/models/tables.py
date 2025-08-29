from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(String, unique=True, nullable=False)
    balance = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_bonus_at = Column(Date, nullable=True)

    stats = relationship("UserStat", back_populates="user")

class Session(Base):
    __tablename__ = 'sessions'
    user_id = Column(String, ForeignKey('users.id'), primary_key=True)
    current_scene_id = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ChoiceLog(Base):
    __tablename__ = 'choices_log'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'))
    from_scene = Column(String)
    to_scene = Column(String)
    choice_text = Column(Text)
    cost = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DailyBonusLog(Base):
    __tablename__ = 'daily_bonus_log'
    user_id = Column(String, ForeignKey('users.id'), primary_key=True)
    date = Column(DateTime(timezone=True), primary_key=True)

class Stat(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)  # например: "quiet", "angry", "reputation"
    name = Column(String, nullable=False)  # например: "Тихоня", "Бунтарка", "Репутация"
    story_id = Column(String, nullable=False)  # чтобы отделить статы по историям

class UserStat(Base):
    __tablename__ = "user_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))  # <= здесь
    stat_id = Column(Integer, ForeignKey("stats.id"))
    value = Column(Integer, default=0)

    user = relationship("User", back_populates="stats")
    stat = relationship("Stat")

