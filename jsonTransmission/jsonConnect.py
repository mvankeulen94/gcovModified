import sys
import optparse
import pymongo
from pymongo import MongoClient
import json
from pprint import pprint
import string

import tornado.httpclient
import tornado.ioloop
import tornado.web
from tornado.escape import json_decode
import motor

def doJSONImport():
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
    parser.add_option("-g", "--githash", dest="ghash",
                      help="git hash of code being tested",
                      default=None)
    parser.add_option("-b", "--buildhash", dest="bhash", 
                      help="build hash of code being tested",
                      default=None)

    parser.add_option("-c", "--connectionstring", dest="connectstr",
                      help="string specifying url",
                      default=None)

    (options, args) = parser.parse_args()
    
    if options.fname is None:
        print "\nERROR: Must specify name of file to import\n"
        sys.exit(-1)
   
    if options.ghash is None:
        print "\nERROR: Must specify git hash \n"
        sys.exit(-1)
    
    if options.bhash is None:
        print "\nERROR: Must specify build hash \n"
        sys.exit(-1)
 
    if options.connectstr is None:
        print "\nERROR: Must specify connection string \n"
        sys.exit(-1)
   
    http_client = tornado.httpclient.HTTPClient()

    for line in open(options.fname, "r"):
        if line == "\n":
            continue
        
        record = json.loads(line)
        record["gitHash"] = options.ghash 
        record["buildHash"] = options.bhash 
        
        request = tornado.httpclient.HTTPRequest(
                                 url=options.connectstr, 
                                 method="POST", 
                                 headers={"Content-Type": "application/json"},
                                 body=json.dumps(record))
        try:
            response = http_client.fetch(request)
            print response.body
        except tornado.httpclient.HTTPError as e:
            print "Error: ", e
    
    http_client.close()

def doJSONAggregate():
    parser = optparse.OptionParser(usage="""\
                                   %prog [database] [collection] [filename]
                                   [gitHash] [buildHash]""")

    # add in command line options. Add mongo host/port combo later
    parser.add_option("-f", "--filename", dest="fname",
                      help="name of file to import",
                      default=None)
    parser.add_option("-g", "--githash", dest="ghash",
                      help="git hash of code being tested",
                      default=None)
    parser.add_option("-b", "--buildhash", dest="bhash", 
                      help="build hash of code being tested",
                      default=None)

    parser.add_option("-c", "--connectionstring", dest="connectstr",
                      help="string specifying url",
                      default=None)

    (options, args) = parser.parse_args()
    
    if options.fname is None:
        print "\nERROR: Must specify name of file to import\n"
        sys.exit(-1)
   
    if options.ghash is None:
        print "\nERROR: Must specify git hash \n"
        sys.exit(-1)
    
    if options.bhash is None:
        print "\nERROR: Must specify build hash \n"
        sys.exit(-1)
 
    if options.connectstr is None:
        print "\nERROR: Must specify connection string \n"
        sys.exit(-1)
   
    http_client = tornado.httpclient.HTTPClient()
    record = {"gitHash": options.ghash, "buildHash": options.bhash}

       
            
    request = tornado.httpclient.HTTPRequest(
                             url="http://127.0.0.1:8888/report",
                             method="POST", 
                             headers={"Content-Type": "application/json"},
                             body=json.dumps(record))
    try:
        response = http_client.fetch(request)
        print response.body
    except tornado.httpclient.HTTPError as e:
        print "Error: ", e
    
    http_client.close()

#doJSONImport()
doJSONAggregate()
