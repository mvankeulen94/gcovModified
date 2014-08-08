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
import json
import datetime 

import pymongo
import tornado.httpclient

def do_json_import():
    """Insert all JSON files from root directory and below into database."""

    parser = optparse.OptionParser(usage="""\
                                   %prog [git_hash] [rootPath]
                                   [build_id] [connectionstring]
                                   [testname] [branch] [platform]""")

    # add in command line options.
    parser.add_option("-g", "--git-hash", dest="ghash",
                      help="git hash of code being tested",
                      default=None)
    parser.add_option("-b", "--build-id", dest="build", 
                      help="build ID of code being tested",
                      default=None)

    parser.add_option("-c", "--connection-string", dest="connectstr",
                      help="URL that will be connected to",
                      default=None)

    parser.add_option("-t", "--test-name", dest="tname",
                      help="name of the test",
                      default=None)

    parser.add_option("-a", "--branch", dest="branch",
                      help="name of the branch",
                      default=None)

    parser.add_option("-p", "--platform", dest="pform",
                      help="build platform",
                      default=None)

    parser.add_option("-r", "--root-dir", dest="root",
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
        for dir_path, sub_dirs, file_names in os.walk(options.root):
            for file_name in file_names:
                if not file_name.endswith(".json"):
                    continue
            
                print "\nNow importing " + file_name + ":\n"

                # Insert the record for a file
                do_import_file(os.path.join(dir_path, file_name), options.ghash, 
                               options.build, options.tname, http_client, 
                               options.connectstr)
    
    else:
        # Import all json files in root directory
        files = [os.path.join(options.root, f) 
                 for f in os.listdir(options.root) if os.path.isfile(os.path.join(options.root, f))]
        for f in files:
            if not f.endswith(".json"):
                continue
            do_import_file(f, options.ghash, options.build, options.tname, 
                           http_client, options.connectstr)

    # Gather meta info
    meta_record = {}
    meta_record["_id"] = {"build_id": options.build,
                         "git_hash": options.ghash}
    meta_record["date"] = options.date 
    meta_record["branch"] = options.branch
    meta_record["platform"] = options.pform
       
    request = tornado.httpclient.HTTPRequest(url=options.connectstr + "/meta", 
                                             method="POST", 
                                             request_timeout=300.0,
                                             body=json.dumps(meta_record))
    try:
        response = http_client.fetch(request)
        print response.body
    except tornado.httpclient.HTTPError as e:
        print "Error: ", e

    http_client.close()


def do_import_file(file_name, git_hash, build_id, test_name, http_client, url):
    """Import contents of a single file into database."""
    with open(file_name, "r") as f:
        for line in f:
            if line == "\n":
                continue
            record = json.loads(line)
            record["git_hash"] = git_hash 
            record["build_id"] = build_id 
            record["test_name"] = test_name 
        
            file_index = record["file"].rfind("/") + 1
            record["dir"] = record["file"][: file_index]
        
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


do_json_import()
