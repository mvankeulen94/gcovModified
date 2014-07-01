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
    parser.add_option("-b", "--buildid", dest="bhash", 
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

    (options, args) = parser.parse_args()
    
    if options.ghash is None:
        print "\nERROR: Must specify git hash \n"
        sys.exit(-1)
    
    if options.bhash is None:
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
    
    # Walk through files in root
    for dirPath, subDirs, fileNames in os.walk(options.root):
        for fileName in fileNames:
            if not fileName.endswith(".json"):
                continue
            
            print "\nNow importing " + fileName + ":\n"
            # Insert the record for a file
            for line in open(os.path.join(dirPath, fileName), "r"):
                if line == "\n":
                    continue
                record = json.loads(line)
                record["gitHash"] = options.ghash 
                record["buildID"] = options.bhash 
                record["testName"] = options.tname

                fileIndex = record["file"].rfind("/") + 1
                record["dir"] = record["file"][: fileIndex]

                # Add meta info
                record["meta"] = {}
                record["meta"]["date"] = str(datetime.datetime.now())
                record["meta"]["branch"] = options.branch
                record["meta"]["platform"] = options.pform
                record["meta"]["gitHash"] = options.ghash 
                record["meta"]["buildID"] = options.bhash 
       
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


doJSONImport()
