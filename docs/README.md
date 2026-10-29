# term-trawler
Aggregate research terms from various sources including support for OMOP tables and OWL files.

## Install
Install the dependencies: 

```bash
pip install -e .
```


## Running the script
#### `just` can be used by specifying the path to the config file in the `justfile`
#### To extract all vocabularies in config file:
`uv run trawler -c {path/to/config/file}` or `just extract`

## Conventions
### Config File
An example config file can be found at `example/config.yaml`

### Source Types
There are three source types for vocabularies. Each type must be specified under `source_type` per vocabulary entry. Each type must include a specific property for the location of the vocabulary terms. (See config example at `example/config.yaml` for more information.)
- OMOP
  - `archive_filename`
- OWL
  - `owl_file`
- FHIR 
  - `source_filename`


## Obtaining Vocabularies
The source vocabulary files or URLs may need to be periodically updated. 

### CDCREC
The details page for CDCREC can can be found on the [CDC Public Health Information Network Vocabulary Access and Distribution System (PHIN VADS)](https://phinvads.cdc.gov/vads/ViewCodeSystem.action?id=2.16.840.1.113883.6.238#) page. The vocabulary can be downloaded [here](https://phinvads.cdc.gov/baseStu3/CodeSystem/2.16.840.1.113883.6.238).

### OMIM
The OMIM vocabulary can be found on the [BioPortal](https://bioportal.bioontology.org/ontologies/OMIM). The source URL for the OWL file can be obtained by right clicking the downloads icon on the top right of the page and copying the link address.

### OMOP Files from Athena
- Create an account on the [Athena](https://athena.ohdsi.org/) website.
- Once created, select the Download tab on top right, which should route to a [list of vocabularies](https://athena.ohdsi.org/vocabulary/list). 
- Select the checkboxes of the vocabularies to download and hit the Download Vocabularies button in the rop right
- Provide bundle name and click Download
- You will receive an email with a link to download the zip file
- The location of where you saved the zip file on your machine will be the `source_filename` in the config file

### UCUM
UCUM is automatically downloaded as a standard, default vocabulary when downloading any vocabulary on [Athena](https://athena.ohdsi.org/). It will not be found in the vocabulary downloads list because it is a mandatory vocabulay loaded automatically in the background.
