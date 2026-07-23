from rdflib import Graph, RDF, OWL

g = Graph()
g.parse("http://edamontology.org/EDAM.owl")

ontology_subjects = list(g.subjects(predicate=RDF.type, object=OWL.Ontology))
for subj in ontology_subjects:
    for pred, obj in g.predicate_objects(subject=subj):
        print(f"{pred} -> {obj}")
