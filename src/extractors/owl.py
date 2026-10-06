import logging
import ssl
import urllib.error
import urllib.request
import xml.sax
import xml.sax._exceptions

import pyhornedowl
import rdflib.plugin
from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS, SKOS
from sqlalchemy.sql.expression import values

from extractors import ExtractorBase
from utils import format_code

logger = logging.getLogger(__name__)


def open_fowl2owl(url: str, ssl_no_verify=False) -> Graph:
    ssl._create_default_https_context = ssl._create_unverified_context
    if ssl_no_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = None
    with urllib.request.urlopen(url, context=ctx) as response:
        data = response.read().decode("utf-8")

    onto = pyhornedowl.open_ontology_from_string(data)

    rdfxml = onto.save_to_string("rdf")

    g = Graph()
    g.parse(data=rdfxml, format="xml", publicID=url)

    logger.info(f"Converted {url} to RDF/XML.")
    return g


def open_owl(url: str, ssl_no_verify=False):
    if ssl_no_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = None
    with urllib.request.urlopen(url, context=ctx) as response:
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

    def _get_replacement_uri(self, g: Graph, subj) -> URIRef | None:
        """Checks both known 'replaced by' predicates and returns whichever is present."""
        for predicate in (
            URIRef("http://purl.obolibrary.org/obo/IAO_0100001"),
            URIRef("http://www.geneontology.org/formats/oboInOwl#replacedBy"),
        ):
            value = g.value(subject=subj, predicate=predicate)
            if isinstance(value, URIRef):
                return value
        return None

    def get_replacement(self, config) -> dict[str, str]:
        g = self._get_graph()
        replacement = {}

        for subj, _, obj in g.triples((None, OWL.deprecated, None)):
            if str(obj).lower() != "true":
                continue

            if not isinstance(subj, URIRef):
                continue

            replacement_curie = self._get_replacement_uri(g, subj)

            if isinstance(replacement_curie, URIRef):
                row = {
                    "concept_code": str(replacement_curie),
                    "vocabulary_prefix": config.get("prefix", ""),
                }
                replacement[
                    format_code(
                        {
                            "concept_code": str(subj),
                            "vocabulary_prefix": config.get("prefix", ""),
                        },
                        config,
                    )
                ] = format_code(row, config)

            # The code below has been commented out because replacement_curie is no longer required in
            # the new model, common_access_model. We are keeping the code in case it is needed in the future
            # else:
            #     replacement[
            #         format_code(
            #             {
            #                 "concept_code": str(subj),
            #                 "vocabulary_prefix": config.get("prefix", ""),
            #             },
            #             config,
            #         )
            #     ] = "OMOP:0"
        return replacement

    def _load_graph(self, url: str, ssl_no_verify=False) -> Graph:
        g = Graph()
        if ssl_no_verify:
            try:
                return open_owl(url, ssl_no_verify=True)
            except (xml.sax.SAXParseException, xml.sax._exceptions.SAXParseException):
                return open_fowl2owl(url, ssl_no_verify=True)
        try:
            g.parse(url)
        except (TimeoutError, urllib.error.URLError, rdflib.plugin.PluginException):
            try:
                g = open_owl(url, ssl_no_verify=False)
            except (xml.sax.SAXParseException, xml.sax._exceptions.SAXParseException):
                g = open_fowl2owl(url, ssl_no_verify=False)
        return g

    @staticmethod
    def _get_definition(g: Graph, subj: URIRef) -> str | None:
        for predicate in DEFINITION_PREDICATES:
            for obj in g.objects(subj, predicate):
                text = str(obj).strip()
                if text:
                    return text
        return None

    def _get_graph(self):
        if getattr(self, "_graph", None) is None:
            file_path = self.config["owl_file"]
            ssl_flag = self.config.get("ssl_no_verify", False)
            self._graph = self._load_graph(file_path, ssl_no_verify=ssl_flag)
        return self._graph

    def extract_data(self, vocabulary_id: str, data_type: str):
        DC = Namespace("http://purl.org/dc/elements/1.1/")
        # file_path = self.config["owl_file"]
        # ssl_flag = self.config.get("ssl_no_verify", False)
        # g = self._load_graph(file_path, ssl_no_verify=ssl_flag)
        g = self._get_graph()
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
                deprecated_flag = g.value(subject=subj, predicate=OWL.deprecated)
                iri = str(subj)
                concept_name = g.value(subject=subj, predicate=RDFS.label)
                definition = self._get_definition(g, subj)
                invalid_reason = None
                if str(deprecated_flag).lower() == "true":
                    replacement_curie = self._get_replacement_uri(g, subj)
                    invalid_reason = (
                        "U" if isinstance(replacement_curie, URIRef) else "D"
                    )
                chunk.append(
                    {
                        "concept_code": iri,
                        "concept_name": str(concept_name) if concept_name else "",
                        "vocabulary_id": self.config.get("prefix", ""),
                        "definition": definition or "",
                        "invalid_reason": invalid_reason,
                    }
                )
                if len(chunk) == ExtractorBase.chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

        elif data_type == "DEPRECATED_CONCEPT":
            chunk = []
            for subj, _, obj in g.triples((None, OWL.deprecated, None)):
                if str(obj).lower() != "true":
                    continue
                if not isinstance(subj, URIRef):
                    continue
                replacement_curie = self._get_replacement_uri(g, subj)
                row: dict[str, str | None] = {
                    "concept_code": str(subj),
                    "deprecation_type": "U"
                    if isinstance(replacement_curie, URIRef)
                    else "D",
                }
                if isinstance(replacement_curie, URIRef):
                    replacement_row: dict[str, str | None] = {
                        "concept_code": str(replacement_curie),
                        "vocabulary_prefix": self.config.get("prefix", ""),
                    }
                    row["replacement_curie"] = format_code(replacement_row, self.config)
                    row["concept_curie"] = format_code(
                        {
                            "concept_code": str(subj),
                            "vocabulary_id": self.config.get("prefix", ""),
                        },
                        self.config,
                    )
                chunk.append(row)
                if len(chunk) == ExtractorBase.chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
