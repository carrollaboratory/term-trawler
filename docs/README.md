# term-trawler
Aggregate research terms from various sources including support for OMOP tables and OWL files.

## Install
Install the dependencies: 

```bash
pip install -e ." 
```


## Running the script
#### `just` can be used by specifying the path to the config file in the `justfile`
#### To extract all vocabularies in config file:
`uv run trawler -c {path/to/config/file}` or `just extract`


#### To extract specific vocabularies, specify the vocabulary prefix separated by comma:
`uv run trawler -c {path/to/config/file} --vocab {prefix1,prefix2}` or `just extract {prefix1,prefix2}`

#### To save term count report to a file, provide the filepath where it should be saved:
`uv run trawler -c {path/to/config/file} --report {path/to/output}` or `just extract "" {path/to/output}`

(If saving report to a file and not specifying vocabularies to extract, `""` must be included before the report output when running the `just` command)



## Conventions
### Config File
An example config file can be found at `example/config.yaml`

### Source Types
There are three source types for vocabularies. Each type must be specified under `source_type` per vocabulary entry. Each type must include a specific property for the location of the vocabulary terms. (See config example at `example/config.yaml` for more information.)
- OMOP
  - `source_filename`
- OWL
  - `owl_file`
- FHIR 
  - `source_filename`
