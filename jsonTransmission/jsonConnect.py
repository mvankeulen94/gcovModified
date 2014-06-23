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
import base64

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.lexers import CLexer
from pygments.lexers import guess_lexer
from pygments.formatters import HtmlFormatter


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

    parser.add_option("-t", "--testname", dest="tname",
                      help="name of the test",
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
   
    if options.tname is None:
        print "\nERROR: Must specify test name \n"
        sys.exit(-1)

    http_client = tornado.httpclient.HTTPClient()

    for line in open(options.fname, "r"):
        if line == "\n":
            continue
        
        record = json.loads(line)
        record["gitHash"] = options.ghash 
        record["buildHash"] = options.bhash 
        record["testName"] = options.tname
        
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

def doJSONAggregate(body):
    http_client = tornado.httpclient.HTTPClient()
    if body == "empty":
        request = tornado.httpclient.HTTPRequest(
                             url="http://127.0.0.1:8080/report",
                             method="GET")
    else:
        request = tornado.httpclient.HTTPRequest(
                             url="http://127.0.0.1:8080/report?" + 
                                 "gitHash=OLDGITHASH234980234809&" + 
                                 "build=OLDBUILDHASH392804",
                             method="GET")

    try:
        response = http_client.fetch(request)
        print response.body
    except tornado.httpclient.HTTPError as e:
        print "Error: ", e
    
    http_client.close()

def getFileContents():
    configfile = raw_input("Please enter config file name: ")
    config = open(configfile, "r")
    configinfo = json.loads(config.readline())
    owner = configinfo["owner"]
    repo = configinfo["repo"]
    path = configinfo["path"]

    url = "https://api.github.com/repos/" + owner + "/" + repo + "/contents/" + path
    http_client = tornado.httpclient.HTTPClient()
    request = tornado.httpclient.HTTPRequest(
            url=url,
            user_agent="Maria's API Test")
    try:
        response = http_client.fetch(request)
        responseDict = json.loads(response.body)
        content = base64.b64decode(responseDict["content"])
        outfile = open("gitcontent.html", "w")
        outfile.write(highlight(content, guess_lexer(content), HtmlFormatter()))
        outfile.close()

    except tornado.httpclient.HTTPError as e:
        print "Error: ", e
    
    http_client.close()
    config.close()


def main():
    response = raw_input("Do you want to:\n 1. import 2. aggregate 3. request file \n")
    if response == "1":
        doJSONImport()
    elif response == "2":
        response = raw_input("Is your GET request:\n 1. empty 2. full \n ")

        if response == "1":
            doJSONAggregate("empty")
        else:
            doJSONAggregate("full")
    else:
        getFileContents()

main()
