import sys
import optparse
import pymongo
from pymongo import MongoClient
import json
from pprint import pprint

def main():
    """Read a JSON file and output the file with added values.

    gitHash and version, which are passed as command line arguments,
    are added to the JSON that is output.
    """
    parser = optparse.OptionParser(usage="""\
                                   %prog [database] [collection] [filename]
                                   [gitHash] [buildHash]""")

    # add in command line options. Add mongo host/port combo later
    parser.add_option("-f", "--filename", dest="fname",
                      help="name of file to import",
                      default=None)
    parser.add_option("-d", "--database", dest="database",
                      help="name of database",
                      default=None)
    parser.add_option("-c", "--collection", dest="collection",
                      help="collection name",
                      default=None)
    parser.add_option("-g", "--githash", dest="ghash",
                      help="git hash of code being tested",
                      default=None)
    parser.add_option("-b", "--buildhash", dest="bhash", 
                      help="build hash of code being tested",
                      default=None)

    (options, args) = parser.parse_args()
    
    if options.database is None:
        print "\nERROR: Must specify database \n"
        sys.exit(-1)
        
    if options.collection is None:
        print "\nERROR: Must specify collection name\n"
        sys.exit(-1)

    if options.fname is None:
        print "\nERROR: Must specify name of file to import\n"
        sys.exit(-1)
   
    if options.ghash is None:
        print "\nERROR: Must specify git hash \n"
        sys.exit(-1)
    
    if options.bhash is None:
        print "\nERROR: Must specify build hash \n"
        sys.exit(-1)
    
    connection = MongoClient()
    db = connection[options.database]
    logs = db[options.collection]
    bulk = logs.initialize_unordered_bulk_op()

    for line in open(options.fname, "r"):
        if line == "\n":
            continue
            
        record = json.loads(line)
        record["gitHash"] = options.ghash 
        record["buildHash"] = options.bhash 
        bulk.insert(record)
    
    try:
        result = bulk.execute()
        pprint(result)
    except BulkWriteError as bwe:
        pprint(bwe.details)

main()
