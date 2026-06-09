# Implementation details for Term Trawler Phase 1

## CLI Application
Extend the application to accept a single YAML configuration. This 
configuration file will have two or three root level headings:

### Warehouse (required for the key configuration)
This section will contain all of the relevant details suitable for connecting
to the database within the given environment the tool is running within. This
should be flexible enough to run safely despite existing as part of a github
repository (i.e. there should be a way to avoid keeping usernames and 
passwords as part of the database URI or as keys). 

### Imports (optional)
This will be an optional section where the user can specify one or more YAML
file that contain terminology details. 

### Terminologies (optional)
This optional section will be a list of terminology definitions with all 
information required to ingest the relevant terms. 

> [!note] 
> At least 1 terminology must be defined either in the root config or one of
> those that are imported.

## Terminology Entry Model

### Core Attributes
The following core attributes should be defined for each terminology entry: 

| Attribute | Data Type | Note |
| --------- | --------- | ---- | 
| Vocabulary Name | String | This should be the human friendly name that will be seen inside the vocabulary table's name field |
| Description | String | Descriptive text, likely pulled from an official source describing the vocabulary's contents and purpose |
| prefix | String | This will be the official prefix that each code will be prefixed with inside the database. |
| FHIR System | String | this will be system used for all terms inside FHIR. Preferably, this will be found at HL7's FHIR docs, however, we may have to fall back to a standard URI | 
| Vocabulary URI | String | This should an well recognized URI for distinctively identifying the vocabulary |
| Source Type | Enumeration | [OMOP, OWL] - This will be used to select which of adapter is to be used to pull the data down.

### Adapter Specific Attributes
| Adapter Type | Attribute | Data Type | Note |
| ------------ | --------- | --------- | ---- | 
| OMOP | vocabulary_id | String | The vocabulary ID associated with the terminology within the OMOP data |
| OMOP | archive_filename | filename | This is the path to the zip file containing the downloaded OMOP data |
| OWL | owl_file | url | This is the URL where the adapter can download the file for loading (i.e. https://github.com/edamontology/edamontology/releases/download/1.25-20251112T1620Z-intermediate/EDAM.owl) |

## Datatype Enumeration
Create an enumeration for datatype that contains the necessary chunks that 
will be extracted (these are just a few OTOH). The idea here will be to 
allow the adapter to change it's behavior and what it returns according
to the data type provided for the call. 

```python
from enum import StrEnum

class ExtractionDataType(StrEnum):
    """Data type to be extracted."""
    VOCABULARY = "vocabulary"
    TERMS = "terms"
    RELATIONSHIPS = "relationships"
    ANCESTORS = "ancestors"
```

## Adapter Pattern Based Extractors
We'll use a simple [adapter pattern](https://refactoring.guru/design-patterns/adapter) 
for our extraction classes so that the extraction loop can be generic letting each
of the instantiated classes do the work specific to the target source. 

### Base Class
Using the python library, abc, define an abstract base class, DataSource with
following interface
  - extract_data(data_type)
  - init function will accept a dictionary which will be the terminology entry from the config



### OMOP Class
Child class properties:
- vocabulary_id
- filename 

The OMOP class will will require as input the source of the OMOP download (zip
file containing multiple text files). When the class is instantiated, it will 
extract the contents of the zip file into a temporary directory. It will throw 
an appropriate exception if it can't be extracted completely.

#### extract_data(data_type, chunk_size)
> [!note] Key Details
> Use [python generators](https://realpython.com/introduction-to-python-generators/?gad_source=1&gad_campaignid=23282418443&gbraid=0AAAAA_bFrtIXJuh2781ZUuhDnI4XRpva8&gclid=CjwKCAjw857RBhAgEiwAI-1yKMb7VipcT_WgGF1laEYdSdXHS9RAg5zRmEzcHJej_mIWMSLX_i2LHRoC7ZcQAvD_BwE) to maintain a tolerable memory footprint.
> 
> Return should be a list of dictionary entries whose keys match the corresponding table 
> specified by the data_type. I recommend using a modular approach to this as well, so 
> that you can easily add more data_types as additional needs are required. 
> 
> For the OMOP, you will basically be extracting data from a specific file, 
> depending on the data_type required. For TERM, you will use CONCEPT. For 
> VOCABULARY, you will probably just pull information from the initial 
> dictionary provided in the init(). 

### OWL Class
Child class properties
- owl_file

For the time being, we can just point rdflib to the online owl file. However, we may need 
to capture a copy first if there is a need to reload from an previous state

Please refer to the [example code](https://github.com/torstees/edam-example) for a quick example on using rdflib to do 
basic parsing of an OWL file. This example shows the basics for the TERM 
extraction as well as pulling some metadata from the owl file that might be 
useful for the VOCABULARY part. For the other data types (currently out of 
scope) more investigation will be required to follow ancesters or gather 
relationship data.

## Piper Data Model 
> Do we need this? This is only necessary if our table names differ from the 
> class names defined inside the LinkML model the SQL Alchemy model was 
> based on. 

To save the data to the database, we can use [piper.datamodel.linkml](https://github.com/carrollaboratory/piper/blob/main/src/piper/datamodel/linkml.py)

This provides the ability to do some data munging in the target model's SQL 
Alchemy classes to work correctly despite the different table names that are 
the result of

## SQL Alchemy Model
Regardless of whether we use the Piper datamodel modifer class or not, we'll 
need to add the SQL Alchemy classes to the [md-terminology-trove](https://github.com/carrollaboratory/md-terminology-trove) 
model as dependencies to the application.

Eric TODO: 
- Add the SQL Alchemy whl file to terminology trove
- Add notes here for how to reference the classes and add as dependency
