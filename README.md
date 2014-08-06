gcovModified
============

##Instructions to run##

###Copy updated gcov files###

```bash
cp gcov.c /local/build/gcc-4.9.0/gcc/
cp list.c /local/build/gcc-4.9.0/gcc/
cp list.h /local/build/gcc-4.9.0/gcc/
```

###Add `list.o` to `GCOV_OBJS` variable in `Makefile.in`###

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
* `list.c`/`list.h` (functions to assist gcov modification)

System information can be found in the `requirements.txt` file.
