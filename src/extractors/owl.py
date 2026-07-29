import logging
import time

from rdflib import OWL, RDF, RDFS, Graph, Namespace

from extractors import ExtractorBase

logger = logging.getLogger(__name__)


class OwlExtractor(ExtractorBase):
    extractor_name = "OWL"

    def __enter__(self):
        return self
        # Entry point for the context manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
        # What happens when context manager is done

    def get_version(self, vocabulary_id: str) -> str | None:
        """This function only gets the first value from the OWL file because there is only
        one Vocabulary value.
        """
        rows = (
            row
            for chunk in self.extract_data(
                vocabulary_id=vocabulary_id,
                data_type="VOCABULARY",
            )
            for row in chunk
        )
        first_row = next(rows, None)
        return first_row.get("vocabulary_version") if first_row else None

    def extract_data(self, vocabulary_id: str, data_type: str):
        OBO = Namespace("http://www.geneontology.org/formats/oboInOwl#")
        DC = Namespace("http://purl.org/dc/elements/1.1/")
        file_path = self.config["owl_file"]
        g = Graph()
        t0 = time.time()
        g.parse(file_path, format="application/rdf+xml")
        if getattr(self, "debug_timing", False):
            logger.error(f"[OwlExtractor] parsing took {time.time() - t0:.1f}s")
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
            chunk = []
            for subj in g.subjects(predicate=RDF.type, object=OWL.Class):
                if not str(subj).startswith("http"):
                    continue  # skip blank nodes
                concept_code = str(subj).rsplit("/", 1)[-1]
                concept_name = g.value(subject=subj, predicate=RDFS.label)
                definition = g.value(subject=subj, predicate=OBO.hasDefinition)
                chunk.append(
                    {
                        "concept_code": concept_code,
                        "concept_name": str(concept_name) if concept_name else "",
                        "vocabulary_id": self.config.get("prefix", ""),
                        "definition": str(definition) if definition else "",
                    }
                )
                if len(chunk) == ExtractorBase.chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
