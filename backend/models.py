"""
SQLAlchemy models for user profiles, people, dosha assignments, and suggestion history.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Profile(Base):
    """A cooking profile (e.g., "Date Night", "Solo Cooking")."""
    __tablename__ = 'profiles'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    people = relationship("Person", back_populates="profile", cascade="all, delete-orphan")
    suggestion_history = relationship("SuggestionHistory", back_populates="profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Profile(id={self.id}, name='{self.name}')>"


class Person(Base):
    """A person in a profile with their dosha constitution and imbalances."""
    __tablename__ = 'people'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    name = Column(String(100), nullable=False)
    serving_count = Column(Integer, default=1, nullable=False)

    # Relationships
    profile = relationship("Profile", back_populates="people")
    dosha_assignments = relationship("DoshaAssignment", back_populates="person", cascade="all, delete-orphan")
    imbalances = relationship("DoshaImbalance", back_populates="person", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}', profile_id={self.profile_id})>"


class DoshaAssignment(Base):
    """Dosha assignment for a person (primary or secondary)."""
    __tablename__ = 'dosha_assignments'

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey('people.id'), nullable=False)
    dosha = Column(String(20), nullable=False)  # 'Vata', 'Pitta', or 'Kapha'
    is_primary = Column(Boolean, default=False, nullable=False)

    # Relationships
    person = relationship("Person", back_populates="dosha_assignments")

    def __repr__(self):
        primary = "primary" if self.is_primary else "secondary"
        return f"<DoshaAssignment(person_id={self.person_id}, dosha='{self.dosha}', {primary})>"


class DoshaImbalance(Base):
    """Specific imbalance a person is experiencing."""
    __tablename__ = 'dosha_imbalances'

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey('people.id'), nullable=False)
    imbalance = Column(String(50), nullable=False)  # Must match seeded imbalance names

    # Relationships
    person = relationship("Person", back_populates="imbalances")

    def __repr__(self):
        return f"<DoshaImbalance(person_id={self.person_id}, imbalance='{self.imbalance}')>"


class SuggestionHistory(Base):
    """Historical record of recipe suggestions for a profile."""
    __tablename__ = 'suggestion_history'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    suggested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    response_json = Column(Text, nullable=False)  # Full Claude response JSON
    people_snapshot = Column(Text, nullable=False)  # JSON snapshot of people at time of suggestion
    graph_recipe_count = Column(Integer, default=0)
    vector_chunk_count = Column(Integer, default=0)

    # Relationships
    profile = relationship("Profile", back_populates="suggestion_history")

    def __repr__(self):
        return f"<SuggestionHistory(id={self.id}, profile_id={self.profile_id}, suggested_at='{self.suggested_at}')>"
