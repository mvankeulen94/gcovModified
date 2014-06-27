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
        self.httpport = conf["httpport"]
        super(Application, self).__init__([
        (r"/", MainHandler),
        (r"/report", ReportHandler),
        (r"/data", DataHandler),
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


class DataHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        self.json_args = json_decode(self.request.body)
        if (self.json_args["gitHash"] == None or self.json_args["buildID"] == None
            or self.json_args["file"] == None):
                self.write("Error!\n")
                return
#        if self.json_args["testName"] == None:
#            self.json_args["testName"] = "all"
        gitHash = self.json_args["gitHash"]
        buildID = self.json_args["buildID"]
        fileName = self.json_args["file"]
        pipeline = [{"$match":{"file": fileName, "gitHash": gitHash, "buildID": buildID}}, {"$project":{"file":1, "lc":1}}, {"$unwind": "$lc"}, {"$group":{"_id": {"file": "$file", "line": "$lc.ln"}, "count":{"$sum": "$lc.ec"}}}]
       
        cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
        result = {}
        result["counts"] = []
        executedLines = []
        nonExecutedLines = []
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            if not "file" in result:
                result["file"] = bsonobj["_id"]["file"]
            result["counts"].append({"l": bsonobj["_id"]["line"], "c": bsonobj["count"]})
        
        self.write(result)
            

class ReportHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments
        
        if len(args) == 0:
            # Get git hashes and build IDs 
            pipeline = [{"$project":{"gitHash":1, "buildID":1}}, 
                        {"$group":{"_id":{"gitHash":"$gitHash", "buildID":"$buildID"}}}]
            cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
            self.write("<html><body>Report:\n")

            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                obj = bsondumps(bsonobj)
                buildID = bsonobj["_id"]["buildID"]
                gitHash = bsonobj["_id"]["gitHash"]
                url = self.request.full_url()
                url += "?gitHash=" + gitHash + "&buildID=" + buildID
                self.write("<a href=\"" + url + "\"> " + buildID + ", " 
                           + gitHash + " </a><br />")
            self.write("</body></html>")

        else:    
            if args.get("gitHash") == None or args.get("buildID") == None:
                self.write("Error!\n")
                return
            # Generate line count results
            gitHash = args.get("gitHash")[0]
            buildID = args.get("buildID")[0]
            self.write(gitHash + ", " + buildID)
            pipeline = [{"$match":{"file": re.compile("^src\/mongo"), 
                         "gitHash": gitHash, "buildID": buildID}}, 
                        {"$project":{"file":1, "lc":1}}, {"$unwind":"$lc"}, 
                        {"$group":{"_id":"$file", "count":{"$sum":1}, 
                         "noexec":{"$sum":{"$cond":[{"$eq":["$lc.ec",0]},1,0]}}}  }]

            cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
            total = 0
            noexecTotal = 0
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                obj = bsondumps(bsonobj)
                count = bsonobj["count"]
                noexec = bsonobj["noexec"]
                total += count
                noexecTotal += noexec

            percentage = float(total-noexecTotal)/total * 100
            self.write("\nlines: " + str(total) + ", hit: " + 
                       str(total-noexecTotal) + ", % executed: " + 
                       str(percentage) + "\n")

            # Generate function results
            pipeline = [{"$project": {"file":1,"functions":1}}, {"$unwind":"$functions"},
                        {"$group": { "_id":"$functions.nm", 
                                     "count" : { "$sum" : "$functions.ec"}}},
                        {"$sort":{"count":-1}}] 
            cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
            noexec = 0
            total = 0
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                count = bsonobj["count"]
                total += 1
                if count == 0:
                    noexec += 1

            percentage = float(total-noexec)/total * 100
            self.write("\nfunctions: " + str(total) + 
                       ", hit: " + str(total-noexec) + 
                       ", % executed: " + str(percentage) + "\n")
        
if __name__ == "__main__":
    application = Application()
    application.listen(application.httpport)
    tornado.ioloop.IOLoop.instance().start()

