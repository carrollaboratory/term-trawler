from collections.abc import Generator
from typing import Any, Dict
from rdflib import Graph, RDF, RDFS, OWL, Namespace


from extractors import ExtractorBase


class OwlExtractor(ExtractorBase):
    extractor_name = "OWL"

    def __enter__(self):
        return self
        # Entry point for the context manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
        # What happens when context manager is done

    def get_version(self, vocabulary_id: str) -> str | None:
        return None



    def extract_data(self, vocabulary_id: str, data_type: str):
        OBO = Namespace("http://www.geneontology.org/formats/oboInOwl#")
        DC = Namespace("http://purl.org/dc/elements/1.1/")
        file_path = self.config["owl_file"]
        g = Graph()
        g.parse(file_path)

        if data_type == "VOCABULARY":
            ontology_subjects = list(g.subjects(predicate=RDF.type, object=OWL.Ontology))
            chunk = []
            for subj in ontology_subjects:
                chunk.append({
                    "vocabulary_name": str(g.value(subject=subj, predicate=DC.title)),
                    "description": str(g.value(subject=subj, predicate=DC.description)),
                    "vocabulary_version": str(g.value(subject=subj, predicate=OWL.versionInfo)),
                })
            yield chunk

        elif data_type == "CONCEPT":
            chunk = []
            for subj in g.subjects(predicate=RDF.type, object=OWL.Class):
                if not str(subj).startswith("http"):
                    continue  # skip blank nodes
                concept_code = str(subj).rsplit("/", 1)[-1]
                concept_name = g.value(subject=subj, predicate=RDFS.label)
                definition = g.value(subject=subj, predicate=OBO.hasDefinition)
                chunk.append({
                    "concept_code": concept_code,
                    "concept_name": str(concept_name) if concept_name else "",
                    "vocabulary_id": self.config.get("prefix", ""),
                    "definition": str(definition) if definition else "",
                })
                if len(chunk) == self.chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
