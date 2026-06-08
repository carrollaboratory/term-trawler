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


## 3. Scope


### In Scope

- Python CLI application to run ingest
- YAML configuration defining each ontology of interest - Ontology Source (OMOP, OWL download path, etc) - FHIR system - Other possible metadata not directly available from the source
- Support for - OMOP source text files - OWL source files (EDAM)


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
| `[md-terminology-trove](https://github.com/carrollaboratory/md-terminology-trove)` | DBT Table data | Database entries within the data warehouse |


### Dependencies

| Package | Version | Purpose | Docs |
|---|---|---|---|
| `[rdflib](https://github.com/RDFLib/rdflib)` | 7.6.0 | This will be used to extract information from OWL files |  |


## 6. Implementation Approach


### Phases

**Phase 1 — [Phase name]**


## 7. Testing Strategy


### Test Cases

| ID | Description | Expected Result |
|---|---|---|
| TC-001 | [What is being tested] | [What success looks like] |


## 11. Appendix



---
*Generated from `design.yaml` on 2026-06-08*
