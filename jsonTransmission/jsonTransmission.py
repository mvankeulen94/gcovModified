import sys
import optparse
import pymongo
from pymongo import MongoClient
import json
from bson.json_util import dumps as bsondumps
import re
from pprint import pprint

import tornado.ioloop
import tornado.web
from tornado.escape import json_decode
import motor
from tornado import gen


class Application(tornado.web.Application):
    def __init__(self):
        configFile = open("config.conf", "r")
        conf = json.loads(configFile.readline())
        configFile.close()
        self.client = motor.MotorClient(conf["hostname"], conf["port"])
        self.db = self.client[conf["database"]]
        self.collection = self.db[conf["collection"]]
        super(Application, self).__init__([
        (r"/", MainHandler),
        (r"/report", ReportHandler),
        ],)

class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        self.write(self.request.headers.get("Content-Type"))
        if self.request.headers.get("Content-Type") == "application/json":
            self.json_args = json_decode(self.request.body)
            result = yield self.application.collection.insert(self.json_args)
            self.write("\nRecord for " + self.json_args.get("file") + 
                       " inserted!\n")
        else:
            self.write("\nError!\n")


class ReportHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        if self.request.headers.get("Content-Type") == "application/json":
            # Get git hashes and build hashes
            pipeline = [{"$project":{"gitHash":1, "buildHash":1}}, 
                        {"$group":{"_id":{"gitHash":"$gitHash", "build":"$buildHash"}}}]
            cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
            self.write("<html><body>Report:\n")

            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                obj = bsondumps(bsonobj)
                build = bsonobj["_id"]["build"]
                gitHash = bsonobj["_id"]["gitHash"]
                url = self.request.full_url()
                url += "?gitHash=" + gitHash + "&build=" + build
                self.write("<a href=\"" + url + "\"> " + build + ", " 
                           + gitHash + " </a><br />")
            self.write("</body></html>")

        else:
            self.write("\nError!\n")
    
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments
        
        if (args.get("gitHash") == None or args.get("build") == None):
            self.write("Error!\n")
            return

        # Generate line count results
        gitHash = args.get("gitHash")[0]
        buildHash = args.get("build")[0]
        self.write(gitHash + ", " + buildHash)
        pipeline = [{"$match":{"file": re.compile("^src\/mongo"), 
                     "gitHash": gitHash, "buildHash": buildHash}}, 
                    {"$project":{"file":1, "lc":1}}, {"$unwind":"$lc"}, 
                    {"$group":{"_id":"$file", "count":{"$sum":1}, 
                     "noexec":{"$sum":{"$cond":[{"$eq":["$lc.ec",0]},1,0]}}}  }]

        cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            obj = bsondumps(bsonobj)
            count = bsonobj["count"]
            noexec = bsonobj["noexec"]
            percentage = float(noexec)/count * 100
            self.write("\nFile: " + bsonobj["_id"] + "\n")
            self.write("lines: " + str(count) + " hit: " + str(count-noexec) + 
                       " % executed: " + str(percentage) + "\n")

        # Generate function results
        pipeline = [{"$project": {"file":1,"functions":1}}, {"$unwind":"$functions"},{"$group": { "_id":"$functions.nm", "count" : { "$sum" : "$functions.ec"}, "noexec":{"$sum":{"$cond":[{"$eq":["$functions.ec",0]},1,0]}}}},{"$sort":{"count":-1}}, {"$limit":10}] 
        cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
        noexec = 0
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            count = bsonobj["count"]
            noexec = bsonobj["noexec"]
            percentage = float(noexec)/count * 100
            if count == 0:
                noexec += 1
            self.write("\nFunction: " + bsonobj["_id"] + "\n")
            self.write("lines: " + str(count) + " hit: " + str(count-noexec) + 
                       " % executed: " + str(percentage) + "\n")
        
if __name__ == "__main__":
    application = Application()
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


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
