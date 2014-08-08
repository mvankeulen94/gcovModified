gcovModified
============

##Instructions to run##

###Copy updated gcov files###

```bash
cp gcov.c /local/build/gcc-4.9.0/gcc/
cp gcov-io.c /local/build/gcc-4.9.0/gcc/
cp gcov-io.h /local/build/gcc-4.9.0/gcc/
```

###Configure gcc###

```bash
./configure --disable-multilib --disable-werror
```

###Build gcc###

```bash
make j4
```

###Run gcov on gcda files###

```bash
for la in $(find -name \*.gcda); do <path_to_gcov> -i $la; done
```

###Set up mongod with SSL connection###

###Add indexes to data collection###
```javascript
db.<collection>.ensureIndex({"build_id": 1, "git_hash": 1, "file": 1})

db.<collection>.ensureIndex({"build_id": 1, "git_hash": 1})

db.<collection>.ensureIndex({"build_id": 1, "git_hash": 1, "test_name": 1, "file": 1})

db.<collection>.ensureIndex({"build_id": 1, "dir":1})

db.<collection>.ensureIndex({"build_id": 1, "file":1})
```
###Set up config file for web app###
`jsonTransmission.py` expects a config file entitled `config.conf` 
in the directory from which `jsonTransmission.py` is run.
The file must contain a dictionary with the following information:

```python
{"hostname": <host_name>, 
 "database": <database_name>, 
 "collection": <main_collection>, 
 "covCollection": <directory_aggregates_collection>, 
 "port": <mongod_port_number>, 
 "client_pem": <path_to_client_pem>, 
 "ca_file": <path_to_ca_file>, 
 "username": <ssl_username>, 
 "httpport": <http_port_number>, 
 "metaCollection": <meta_info_collection>, 
 "github_token": <github_token>}
```

Note that the information must be entirely in one line.

###Run web app###
```bash
python <path_to_jsonTransmission.py> &
```

###Run import program###
```bash
python <path_to_jsonImport.py> -b <build_id> -g <git_hash> -c <connection_url> -t <test_name> -a <branch_name> -p <platform_name> -r <root_directory> -d <build_date>
```

##General Info##

gcovModified is an easily extensible code coverage utility intended for integration with MongoDB's 
build system. It stores and displays coverage information obtained from gcc's code coverage utility
gcov. It allows users to filter their coverage results by test suite. Additionally, users can use
the build comparison feature to determine the coverage changes between two revisions of the source.

The source of the program consists of several components:
* `jsonTransmission.py` (the web app component)
* `jsonImport.py` (the data import program)
* `gcov.c` (the modified gcov source from gcc 4.9.0)
* `gcov-io.c`/`gcov-io.h` (updated gcov files containing helper functions for coverage display)

System information can be found in the `requirements.txt` file.

##To do##
* Add option in `jsonImport.py` to specify pattern of file names to 
import. 
* Add option in `jsonTransmission.py` to select alternate directories
besides `src/mongo` to search for build/git hash coverage results

