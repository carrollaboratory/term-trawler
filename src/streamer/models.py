from typing import Optional

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Concept(Base):
    __tablename__ = "concept"

    id: Mapped[int] = mapped_column(primary_key=True)
    ontology_id: Mapped[str]
    concept_id: Mapped[str]
    concept_code: Mapped[str]
    display: Mapped[Optional[str]]  # noqa
    definition: Mapped[Optional[str]]  # noqa
    version: Mapped[str]


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id: Mapped[int] = mapped_column(primary_key=True)
    ontology_id: Mapped[str]
    name: Mapped[Optional[str]]  # noqa
    ontology_uri: Mapped[str]
    fhir_system: Mapped[str]
    prefix: Mapped[Optional[str]]  # noqa
    description: Mapped[Optional[str]]  # noqa
    source: Mapped[Optional[str]]  # noqa
