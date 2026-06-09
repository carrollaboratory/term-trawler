# Term Trawler

![status](https://img.shields.io/badge/status-draft-yellow) ![version](https://img.shields.io/badge/version-0.1.0-lightgrey)

| | |
|---|---|
| **Author** | Eric Torstenson |
| **Created** | 2026-06-08 |
| **Updated** | 2026-06-08 |
| **Reviewers** | — |


## 1. Overview

Pulls all relevant terminologies from external sources into the DBT database using schema, [terminology-trove](https://github.com/carrollaboratory/md-terminology-trove)


### Goals

- Create internal representation of all terms used by the studies used in our transformations.
- Provide additional details such as FHIR Systems that will be used by downstream transforms.
- Provide additional details that may be useful for analysts, such as harmonization details found inside the sources as well as parent/child relationships


### Non-Goals

- This will not capture all possible details associated with each term, only those relevant to our ETL and analytical needs


## 2. Context & Motivation


### Background

The data flowing through the ETL process will land with a large number of public terms which provide a number of challenges:
 - These terms must be able to be validated for correctness
 - While the curies are sufficiently distinct, additional context may be important downstream users (or ETL engineers)
 - Key meta data, like FHIR Systems, must be defined in a central location


### Motivation

Validation can be done using external APIs, but would require processing external to DBT. Additional metadata is currently not supported by the access model, making information like displays unavailable.


### References

- [Implementation Details](design/phase1-details)


## 3. Scope


### In Scope

- Python CLI application to run ingest
- YAML configuration defining each ontology of interest - Ontology Source (OMOP, OWL download path, etc) - FHIR system - Other possible metadata not directly available from the source
- {'Support for': ['OMOP source text files', 'OWL source files (EDAM)']}
- Table Support - Vocabulary - Concept


### Out of Scope

- For now, we are focussing on only the vocabularies from OMOP and ontologies available in OWL format


## 4. Stakeholders

| Role | Name | Responsibilities |
|---|---|---|
| Developer | Yelean Cox | Application Developer |


## 5. Technical Design


### Architecture

Trawler Ingest - Basic wrapper that loads the configuration to determine which terminologies are to be found and how they are to be harvested.


#### Components

| Component | Technology | Description |
|---|---|---|
| **Trawler** | `Python w/ YAML config` | Main application that loads YAML config and iterates over each of
terminologies and runs the appropriate ingest calls
 |
| **Term Extractor** | `` | Adapter pattern to allow the trawler to load data from varied
sources using a common interface. Initial adapters include: OMOP,
OWL
 |
| **Term Loader** | `` | Loads data into the defined schema the [SQL Alchemy interface](https://github.com/carrollaboratory/piper/blob/main/src/piper/datamodel/linkml.py). This
will require the DBT staging template name as well as the target
model's SQL Alchemy model added as a dependency to the execution
repository.
 |


### Interfaces


#### Inputs

| Name | Format | Description |
|---|---|---|
| `YAML Configuration` | YAML | Configuration containing details relating to each of the vocabularies
 |
| `OMOP Flat File` | TSV Format | For convenience, we can pull most of our terms from OMOP downloads.
These files can either be loaded into a RDB and queried or parsed
directly.
 |
| `OWL File` | OWL | OWL is a robust, logic-based Semantic Web standard used to author
ontologies.
 |


#### Outputs

| Name | Format | Description |
|---|---|---|
| `md-terminology-trove` | DBT Table data | [md-terminology-trove](https://github.com/carrollaboratory/md-terminology-trove) is a schema whose data entries live within the data warehouse |


### Dependencies

| Package | Version | Purpose | Docs |
|---|---|---|---|
| `rdflib` | 7.6.0 | [rdflib](https://github.com/RDFLib/rdflib) will be used to extract information from OWL files |  |


## 6. Implementation Approach


### Strategy

A very basic CLI application that accepts a single YAML configuration that identifies which terminologies to load, the source for each of those terminologies and any additional metadata necessary for loading this data. Support for various source types and additional metadata can be added in separate stages.


### Phases

**Phase 1 — Core Process**

Basic CLI application will allow the application to be run either on a
laptop or as part of an orchestrated pipeline. Components include:
  - CLI application
  - YAML Configuration direction to control ingestion and DB connection
  - Base adapter model
  - Source OMOP adapter
  - Source OWL adapter



### Error Handling

- Core Python exceptions will be used where suitable. - Basic DB connection issues will immediately halt. - Schema related issues will also cause hard stop


### Logging

WARNING and ERROR logging used appropriately INFO Level will include
  - Successful database connections
  - Vocabulary section and which adapter type is being used
  - filenames and URLs that are successfully acquired and processed
  - High level summary of DB entries added/updated
DEBUG Level will include
  - SQL Statements if we are writing our own SQL
  - HTTP responses where appropriate
  - Complete record rows when using with a serialization library instead of SQL


## 7. Testing Strategy


### Test Cases

| ID | Description | Expected Result |
|---|---|---|
| TC-001 | [What is being tested] | [What success looks like] |


## 8. Risks & Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-001 | Large input data may be too large for some tooling | low | low | We'll be streaming most of the data directly from file to avoid data
loading restrictions for large data components like OMOP.
 |
| R-002 | rdflib is unfamiliar and may not handle EDAM correctly | low | low | No one on the team has used this library before. If there are issues
using the library, we will have to fall back to searching for an
alternative approach to loading data in OWL format.
 |


## 10. Decision Log


### D-001 — Streaming flat TSV content is sufficient

**Date:** 2026-06-09  
**Rationale:** We can maintain a low memory profile without adding extra deps

**Alternatives considered:**
- I was considering dumping to database and then streaming from there, but this seems good enough


### D-002 — rdflib seems to work OK with EDAM

**Date:** 2026-06-09  
**Rationale:** Claude generated a simple test example and it looks fine for a quick glance and the interface looks reasonable.

**Alternatives considered:**
- This simply confirms we aren't likely to need to find an alternative


## 11. Appendix


### Glossary

| Term | Definition |
|---|---|
| **Vocabulary** | Standized public terminology. This is interchangeable with Ontology we've used over the last few years.  |
| **Concept** | This is just a single code within a vocabulary. This is somewhat synonymous with our Term or Code. |



---
*Generated from `design.yaml` on 2026-06-09*
