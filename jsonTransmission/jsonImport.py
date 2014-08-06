 #    Copyright (C) 2014 MongoDB Inc.
 #
 #    This program is free software: you can redistribute it and/or  modify
 #    it under the terms of the GNU Affero General Public License, version 3,
 #    as published by the Free Software Foundation.
 #
 #    This program is distributed in the hope that it will be useful,
 #    but WITHOUT ANY WARRANTY; without even the implied warranty of
 #    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 #    GNU Affero General Public License for more details.
 #
 #    You should have received a copy of the GNU Affero General Public License
 #    along with this program.  If not, see <http://www.gnu.org/licenses/>.
 #
 #    As a special exception, the copyright holders give permission to link the
 #    code of portions of this program with the OpenSSL library under certain
 #    conditions as described in each individual source file and distribute
 #    linked combinations including the program with the OpenSSL library. You
 #    must comply with the GNU Affero General Public License in all respects for
 #    all of the code used other than as permitted herein. If you modify file(s)
 #    with this exception, you may extend this exception to your version of the
 #    file(s), but you are not obligated to do so. If you do not wish to do so,
 #    delete this exception statement from your version. If you delete this
 #    exception statement from all source files in the program, then also delete
 #    it in the license file.

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
                                   %prog [git_hash] [rootPath]
                                   [build_id] [connectionstring]
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

    parser.add_option("-d", "--date", dest="date",
                      help="date of build",
                      default=None)

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

    if options.date is None:
        print "\nERROR: Must specify date \n"
        sys.exit(-1)

    http_client = tornado.httpclient.HTTPClient()

    # Check if date is properly formatted 
    date = datetime.datetime.strptime(options.date, "%Y-%m-%dT%H:%M:%S.%f")
 
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
    metaRecord["_id"] = {"build_id": options.build,
                         "git_hash": options.ghash}
    metaRecord["date"] = options.date 
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


def doImportFile(fileName, git_hash, build_id, testName, http_client, url):
    """Import contents of a single file into database."""
    for line in open(fileName, "r"):
        if line == "\n":
            continue
        record = json.loads(line)
        record["git_hash"] = git_hash 
        record["build_id"] = build_id 
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
