import string
import os
import sys
import optparse
import pymongo
import json
import tornado.httpclient
import datetime 

def doJSONImport():
    """Insert all JSON files from root directory and below into database."""

    parser = optparse.OptionParser(usage="""\
                                   %prog [gitHash] [rootPath]
                                   [buildID] [connectionstring]
                                   [testname] [branch] [platform]""")

    # add in command line options. Add mongo host/port combo later
    parser.add_option("-g", "--githash", dest="ghash",
                      help="git hash of code being tested",
                      default=None)
    parser.add_option("-b", "--buildid", dest="build", 
                      help="build ID of code being tested",
                      default=None)

    parser.add_option("-c", "--connectionstring", dest="connectstr",
                      help="string specifying url",
                      default=None)

    parser.add_option("-t", "--testname", dest="tname",
                      help="name of the test",
                      default=None)

    parser.add_option("-a", "--branch", dest="branch",
                      help="name of the branch",
                      default=None)

    parser.add_option("-p", "--platform", dest="pform",
                      help="build platform",
                      default=None)

    parser.add_option("-r", "--rootdir", dest="root",
                      help="root directory of JSON files",
                      default=None)

    parser.add_option("--recursive", dest="recurse",
                      help="make import recursive",
                      action="store_true",
                      default=False)

    (options, args) = parser.parse_args()
    
    if options.ghash is None:
        print "\nERROR: Must specify git hash \n"
        sys.exit(-1)
    
    if options.build is None:
        print "\nERROR: Must specify build ID \n"
        sys.exit(-1)
 
    if options.connectstr is None:
        print "\nERROR: Must specify connection string \n"
        sys.exit(-1)
   
    if options.tname is None:
        print "\nERROR: Must specify test name \n"
        sys.exit(-1)

    if options.branch is None:
        print "\nERROR: Must specify branch name \n"
        sys.exit(-1)

    if options.pform is None:
        print "\nERROR: Must specify platform \n"
        sys.exit(-1)

    if options.root is None:
        print "\nERROR: Must specify root directory \n"
        sys.exit(-1)

    http_client = tornado.httpclient.HTTPClient()
   
    if options.recurse:
        # Walk through files in root
        for dirPath, subDirs, fileNames in os.walk(options.root):
            for fileName in fileNames:
                # TODO: Add option to specify pattern
                if not fileName.endswith(".json"):
                    continue
            
                print "\nNow importing " + fileName + ":\n"

                # Insert the record for a file
                doImportFile(os.path.join(dirPath, fileName), options.ghash, options.build, options.tname, http_client, options.connectstr)
    
    else:
        # Import all json files in current directory
        files = [os.path.join(options.root, f) for f in os.listdir(options.root) if os.path.isfile(os.path.join(options.root, f))]
        for f in files:
            # TODO: Add option to specify pattern
            if not f.endswith(".json"):
                continue
            doImportFile(f, options.ghash, options.build, options.tname, http_client, options.connectstr)

    # Gather meta info
    metaRecord = {}
    metaRecord["_id"] = {"buildID": options.build,
                         "gitHash": options.ghash}
    metaRecord["date"] = str(datetime.datetime.now())
    metaRecord["branch"] = options.branch
    metaRecord["platform"] = options.pform
       
    request = tornado.httpclient.HTTPRequest(url=options.connectstr + "/meta", 
                                             method="POST", 
                                             request_timeout=300.0,
                                             body=json.dumps(metaRecord))
    try:
        response = http_client.fetch(request)
        print response.body
    except tornado.httpclient.HTTPError as e:
        print "Error: ", e

    http_client.close()


def doImportFile(fileName, gitHash, buildID, testName, http_client, url):
    """Import contents of a single file into database."""
    for line in open(fileName, "r"):
        if line == "\n":
            continue
        record = json.loads(line)
        record["gitHash"] = gitHash 
        record["buildID"] = buildID 
        record["testName"] = testName 
    
        fileIndex = record["file"].rfind("/") + 1
        record["dir"] = record["file"][: fileIndex]
    
        request = tornado.httpclient.HTTPRequest(
                                             url=url,
                                             method="POST", 
                                             headers={"Content-Type": "application/json"},
                                             request_timeout=300.0,
                                             body=json.dumps(record))
        try:
            response = http_client.fetch(request)
            print response.body
        except tornado.httpclient.HTTPError as e:
            print "Error: ", e


doJSONImport()
