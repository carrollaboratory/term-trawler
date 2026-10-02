import logging
import ssl
import urllib.error
import urllib.request
import xml.sax

import pyhornedowl
import rdflib.plugin
from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS, SKOS

from extractors import ExtractorBase

logger = logging.getLogger(__name__)


def open_fowl2owl(url: str) -> Graph:
    ssl._create_default_https_context = ssl._create_unverified_context

    with urllib.request.urlopen(url) as response:
        data = response.read().decode("utf-8")

    onto = pyhornedowl.open_ontology_from_string(data)

    rdfxml = onto.save_to_string("rdf")

    g = Graph()
    g.parse(data=rdfxml, format="xml", publicID=url)

    logger.info(f"Converted {url} to RDF/XML.")
    return g


def open_owl(url: str):
    with urllib.request.urlopen(url) as response:
        data = response.read()

    g = Graph()
    g.parse(data=data, format="xml", publicID=url)

    return g


ENTITY_TYPES = [
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.NamedIndividual,
]

DEFINITION_PREDICATES = (
    SKOS.definition,
    URIRef("http://www.geneontology.org/formats/oboInOwl#hasDefinition"),
    URIRef("http://purl.obolibrary.org/obo/IAO_0000115"),
    DCTERMS.description,
    RDFS.comment,
)


class OwlExtractor(ExtractorBase):
    extractor_name = "OWL"

    def __enter__(self):
        print("Parsing OWL file")
        return self
        # Entry point for the context manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
        # What happens when context manager is done

    def get_version(self, vocabulary_id: str) -> str | None:
        """When extracting data_type==VOCABULARY, only one row should ever be returned
        due to the nature of the query."""
        first_row = next(
            self.extract_data(
                vocabulary_id=vocabulary_id,
                data_type="VOCABULARY",
            )
        )[0]
        return first_row.get("vocabulary_version") if first_row else None

    def get_replacement(self, config) -> dict[str, str]:
        return {}

    def _load_graph(self, url: str) -> Graph:
        g = Graph()
        try:
            g.parse(url)
        except (TimeoutError, urllib.error.URLError, rdflib.plugin.PluginException):
            g = open_owl(url)
        except xml.sax.SAXParseException:
            g = open_fowl2owl(url)
        return g

    @staticmethod
    def _get_definition(g: Graph, subj: URIRef) -> str | None:
        for predicate in DEFINITION_PREDICATES:
            for obj in g.objects(subj, predicate):
                text = str(obj).strip()
                if text:
                    return text
        return None

    def extract_data(self, vocabulary_id: str, data_type: str):
        DC = Namespace("http://purl.org/dc/elements/1.1/")
        file_path = self.config["owl_file"]
        g = self._load_graph(file_path)
        if data_type == "VOCABULARY":
            ontology_subjects = list(
                g.subjects(predicate=RDF.type, object=OWL.Ontology)
            )
            if len(ontology_subjects) > 1:
                logger.warning("More than one vocabulary received.")
            chunk = []
            for subj in ontology_subjects:
                vocab_name = g.value(subject=subj, predicate=DC.title)
                description = g.value(subject=subj, predicate=DC.description)
                version = g.value(subject=subj, predicate=OWL.versionInfo)
                chunk.append(
                    {
                        "vocabulary_name": str(vocab_name) if vocab_name else "",
                        "description": str(description) if description else "",
                        "vocabulary_version": str(version) if version else "",
                    }
                )
            yield chunk

        elif data_type == "CONCEPT":
            subjects = set()
            for entity_type in ENTITY_TYPES:
                for subj in g.subjects(predicate=RDF.type, object=entity_type):
                    if isinstance(subj, URIRef):
                        subjects.add(subj)
            chunk = []
            for subj in sorted(subjects):
                iri = str(subj)
                concept_name = g.value(subject=subj, predicate=RDFS.label)
                definition = self._get_definition(g, subj)
                chunk.append(
                    {
                        "concept_code": iri,
                        "concept_name": str(concept_name) if concept_name else "",
                        "vocabulary_id": self.config.get("prefix", ""),
                        "definition": definition or "",
                    }
                )
                if len(chunk) == ExtractorBase.chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
