# Shrimp Basket

When you prefer a bitesized portion of vocabulary terms instead of the entire
ocean, use shrimp-basket to prune the list to a size better suited for the
environment (such as AnVIL).

## Basic usage

`shrimp-basket` accepts a 2 column CSV file (with headers), harmonizes those
prefixes to match those inside our warehouse and then builds corresponding
Concept and Vocabulary CSV files that can be used for easy ingestion into your
mini-warehouse.

### Curie Input Format

The format is simple:

| Column Name | Description                                                                                            |
| ----------- | ------------------------------------------------------------------------------------------------------ |
| curie       | The curie or code to be matched                                                                        |
| prefix      | If 'curie' is actually a code that is expected to come from a particular vocabulary, this will be used |

### Example Curie List file

| curie       | prefix |
| ----------- | ------ |
| 1234abc     | hp     |
| 0000001     | hp     |
| HP:0000973  |        |
| HP:0001067  |        |
| HP:0001169  |        |
| HPO:0001171 |        |
| hpo:0002018 |        |
| 0002104     | HPO    |
| (etc)       |

### Curie Harmonization

Before any term matching is performed, those prefixes will be harmonized using
the various synonyms from
[term-wyrm](https://github.com/carrollaboratory/term-wyrm/blob/main/src/term_wyrm/data/vocabulary_details.csv).
If you need additional synonyms, we can add them via PRs.

Once harmonization has completed, a file named, curie_harmonization.csv is
written to the output directory with the details required to transform the
existing prefixes inside dbt:

| curie       | prefix | harmonized_curie |
| ----------- | ------ | ---------------- |
| 1234abc     | hp     | HP:1234abc       |
| 0000001     | hp     | HP:0000001       |
| HP:0000973  | HP     | HP:0000973       |
| HP:0001067  | HP     | HP:0001067       |
| HP:0001169  | HP     | HP:0001169       |
| HPO:0001171 | HPO    | HP:0001171       |
| hpo:0002018 | hpo    | HP:0002018       |

### Concept and Vocabulary Matches

For each concept matching the harmonized curies, a corresponding Concept entry
will be provided in the file, concept.csv. Also, all necessary Vocabulary
entries will also be provided in a new file, vocabulary.csv.

#### Concept Output Example

| concept_curie | concept_id | vocabulary_prefix | concept_code | display                      | definition |
| ------------- | ---------- | ----------------- | ------------ | ---------------------------- | ---------- |
| HP:0000001    | 37420594   | HP                | 0000001      | All                          |            |
| HP:0000002    | 37420604   | HP                | 0000002      | Abnormality of body height   |            |
| HP:0000003    | 37420605   | HP                | 0000003      | Multicystic kidney dysplasia |            |
| HP:0000005    | 37420606   | HP                | 0000005      | Mode of inheritance          |            |
| HP:0000093    | 37420686   | HP                | 0000093      | Proteinuria                  |            |
| HP:0000639    | 37421100   | HP                | 0000639      | Nystagmus                    |            |
| HP:0000771    | 37421203   | HP                | 0000771      | Gynecomastia                 |            |
| HP:0000973    | 37420595   | HP                | 0000973      | Cutis laxa                   |            |
| HP:0001067    | 37420596   | HP                | 0001067      | Neurofibroma                 |            |
| HP:0001169    | 37420597   | HP                | 0001169      | Broad palm                   |            |

#### Vocabulary Output Example

| vocabulary_prefix | name                                                          | vocabulary_uri                              | vocabulary_id | fhir_system                              | description                                                                                                                                                                                                                                                                           | version                                                                                                      | vocabulary_source                             |
| ----------------- | ------------------------------------------------------------- | ------------------------------------------- | ------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------- |
| MONDO             | Mondo Disease Ontology                                        | http://purl.obolibrary.org/obo/MONDO_[code] | MONDO         | http://purl.obolibrary.org/obo/mondo.owl | The Mondo Disease Ontology (Mondo) aims to harmonize disease definitions across the world.                                                                                                                                                                                            |                                                                                                              | OWL - http:/purl.obolibrary.org/obo/mondo.owl |
| HP                | Human Phenotype Ontology                                      | http://purl.obolibrary.org/obo/HP_[code]    | HPO           | http://purl.obolibrary.org/obo/hp.owl    | The Human Phenotype Ontology (HPO) aims to provide a standardized vocabulary of phenotypic abnormalities encountered in human disease.                                                                                                                                                | HPO v2026-06-23                                                                                              | OMOP - vocabulary_20261109.zip                |
| snomedct          | Systematic Nomenclature of Medicine - Clinical Terms (IHTSDO) | http://snomed.info/id/[code]                | SNOMED        | http://snomed.info/sct                   | "SNOMED CT (Systematized Nomenclature of Medicine -- Clinical Terms), is a systematically organized computer processable collection of medical terminology covering most areas of clinical information such as diseases, findings, procedures, microorganisms, pharmaceuticals, etc." | 2026-02-01 SNOMED CT International Edition; 2026-03-01 SNOMED CT US Edition; 2026-04-08 SNOMED CT UK Edition | OMOP - vocabulary_20261109.zip                |

#### Unmatched Curies

Any Curies provided with no suitable match are written to the file,
unmatched_curies.csv. This file is only written if anything is not matched.

| curie   | prefix | harmonized_curie |
| ------- | ------ | ---------------- |
| 1234abc | hp     | HP:1234abc       |

### Example run

```bash
$ head tests/fixtures/curie_list.csv
curie,prefix
1234abc,hp
0000001,hp
HP:0000973,
HP:0001067 ,
 HP:0001169,
HPO:0001171,
hpo:0002018,
0002104,HPO

$ shrimp-basket --curie-file tests/fixtures/curie_list.csv -c config.yaml -o output/test1
12:24:12 INFO     You have chosen to use: Namespace(log_level='INFO', curie_file='tests/fixtures/curie_list.csv', curie=None, harmonize_prefix=False,                   shrimp.py:218
                  config='config.yaml', outdir='output/test1')
         INFO     Patching module: 'common_access_model.datamodel.common_access_model_sqla'                                                                             linkml.py:204
         INFO     76 tables patched                                                                                                                                     linkml.py:218
         WARNING  1 curie(s) not found in the database: ['HP:1234abc']                                                                                                  shrimp.py:238
         INFO     Found 60 concept(s) across 3 vocabularies

$ head output/test1/*.csv
==> output/test1/concepts.csv <==
concept_curie,concept_id,vocabulary_prefix,concept_code,display,definition
HP:0000001,37420594,HP,0000001,All,
HP:0000002,37420604,HP,0000002,Abnormality of body height,
HP:0000003,37420605,HP,0000003,Multicystic kidney dysplasia,
HP:0000005,37420606,HP,0000005,Mode of inheritance,
HP:0000093,37420686,HP,0000093,Proteinuria,
HP:0000639,37421100,HP,0000639,Nystagmus,
HP:0000771,37421203,HP,0000771,Gynecomastia,
HP:0000973,37420595,HP,0000973,Cutis laxa,
HP:0001067,37420596,HP,0001067,Neurofibroma,

==> output/test1/curie_harmonization.csv <==
curie,prefix,harmonized_curie
1234abc,hp,HP:1234abc
0000001,hp,HP:0000001
HP:0000973,HP,HP:0000973
HP:0001067,HP,HP:0001067
HP:0001169,HP,HP:0001169
HPO:0001171,HPO,HP:0001171
hpo:0002018,hpo,HP:0002018
0002104,HPO,HP:0002104
0002105,hpo,HP:0002105

==> output/test1/unmatched_curies.csv <==
curie,prefix,harmonized_curie
1234abc,hp,HP:1234abc

==> output/test1/vocabulary.csv <==
vocabulary_prefix,name,vocabulary_uri,vocabulary_id,fhir_system,description,version,vocabulary_source
MONDO,Mondo Disease Ontology,http://purl.obolibrary.org/obo/MONDO_[code],MONDO,http://purl.obolibrary.org/obo/mondo.owl,The Mondo Disease Ontology (Mondo) aims to harmonize disease definitions across the world.,,OWL - http:/purl.obolibrary.org/obo/mondo.owl
HP,Human Phenotype Ontology,http://purl.obolibrary.org/obo/HP_[code],HPO,http://purl.obolibrary.org/obo/hp.owl,The Human Phenotype Ontology (HPO) aims to provide a standardized vocabulary of phenotypic abnormalities encountered in human disease.,HPO v2026-06-23,OMOP - vocabulary_20261109.zip
snomedct,Systematic Nomenclature of Medicine - Clinical Terms (IHTSDO),http://snomed.info/id/[code],SNOMED,http://snomed.info/sct,"SNOMED CT (Systematized Nomenclature of Medicine -- Clinical Terms), is a systematically organized computer processable collection of medical terminology covering most areas of clinical information such as diseases, findings, procedures, microorganisms, pharmaceuticals, etc.",2026-02-01 SNOMED CT International Edition; 2026-03-01 SNOMED CT US Edition; 2026-04-08 SNOMED CT UK Edition,OMOP - vocabulary_20261109.zip
```
