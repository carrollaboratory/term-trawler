from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Concept(Base):
    __tablename__ = "concept"

    id: Mapped[int] = mapped_column(primary_key=True)
    ontology_id: Mapped[str]
    concept_id: Mapped[str]
    concept_code: Mapped[str]
    display: Mapped[str]
    definition: Mapped[str]
    version: Mapped[str]


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id: Mapped[int] = mapped_column(primary_key=True)
    ontology_id: Mapped[str]
    name: Mapped[str]
    ontology_url: Mapped[str]
    fhir_system: Mapped[str]
    prefix: Mapped[str]
    description: Mapped[str]
    source: Mapped[str]
