import sys
import pymongo 
from pymongo import MongoClient
import json

def main():
    """Read a JSON file and output the file with added values.

    gitHash and version, which are passed as command line arguments,
    are added to the JSON that is output.
    """

    if len(sys.argv) < 3:
        print "Usage: python jsonTransmission.py <gitHash> <version>"
        sys.exit(1)
  
    filename = raw_input("Please enter file name: ")
    f = open(filename, "r")
    databaseName = raw_input("Please enter database name: ")
    collectionName = raw_input("Please enter collection name: ")

    for line in f:
        firstBrace = line.find('{')
        if firstBrace != -1:
            client = MongoClient()
            db = client[databaseName]
            collection = db[collectionName]
            
            record = json.loads(line)
            record["gitHash"] = sys.argv[1]
            record["version"] = sys.argv[2]
            collection.insert(record)

    f.close() 

main()
