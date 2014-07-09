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
import ssl
import tornado.httpclient

import pipelines

import urllib


class Application(tornado.web.Application):
    def __init__(self):
        configFile = open("config.conf", "r")
        conf = json.loads(configFile.readline())
        configFile.close()
        self.client = motor.MotorClient(host=conf["hostname"], port=conf["port"], 
                                        ssl=True, ssl_certfile=conf["clientPEM"], 
                                        ssl_cert_reqs=ssl.CERT_REQUIRED, 
                                        ssl_ca_certs=conf["CAfile"])

        self.client.the_database.authenticate(conf["username"], mechanism="MONGODB-X509")

        self.db = self.client[conf["database"]]
        self.collection = self.db[conf["collection"]]
        self.metaCollection = self.db[conf["metaCollection"]]
        self.covCollection = self.db[conf["covCollection"]]
        self.httpport = conf["httpport"]
       
        super(Application, self).__init__([
        (r"/", MainHandler),
        (r"/report", ReportHandler),
        (r"/data", DataHandler),
        (r"/meta", MetaHandler),
        ],)


class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        self.write(self.request.headers.get("Content-Type"))
        if self.request.headers.get("Content-Type") == "application/json":
            self.json_args = json_decode(self.request.body)
      
            # Insert information
            result = yield self.application.collection.insert(self.json_args)
            self.write("\nRecord for " + self.json_args.get("file") + 
                       " inserted!\n")
        else:
            self.write("\nError!\n")


class DataHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        url = self.request.full_url()[-len(self.request.uri):]
        args = self.request.arguments
        query = {}
        cursor = None # Cursor with which to traverse query results
        result = None # Dictionary to store query result
        gitHash = args.get("gitHash")[0]
        buildID = args.get("buildID")[0]
        if "dir" in args:
            directory = urllib.unquote(args.get("dir")[0])
            # Get line results
            results = {} # Store coverage data
            pipeline = [{"$match":{"file": re.compile("^" + directory), "gitHash": gitHash, "buildID": buildID}}, {"$project":{"file":1, "lc":1}}, {"$unwind": "$lc"}, {"$group":{"_id": {"file": "$file", "line": "$lc.ln"}, "count":{"$sum": "$lc.ec"}}}]

            cursor = yield self.application.collection.aggregate(pipeline, cursor={})
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                amountAdded = 0
                if bsonobj["count"] != 0:
                    amountAdded = 1

                # Check if there exists an entry for this file
                if bsonobj["_id"]["file"] in results:
                    results[bsonobj["_id"]["file"]]["lineCovCount"]+= amountAdded
                    results[bsonobj["_id"]["file"]]["lineCount"] += 1

                # Otherwise, create a new entry
                else:
                    results[bsonobj["_id"]["file"]] = {}
                    results[bsonobj["_id"]["file"]]["lineCovCount"] = amountAdded
                    results[bsonobj["_id"]["file"]]["lineCount"] = 1

            # Get function results
            pipeline = [{"$match":{"file": re.compile("^" + directory), "gitHash": gitHash, "buildID": buildID}}, {"$project": {"file":1,"functions":1}}, {"$unwind":"$functions"}, {"$group": { "_id": {"file": "$file", "function": "$functions.nm"}, "count" : { "$sum" : "$functions.ec"}}}]
            cursor = yield self.application.collection.aggregate(pipeline, cursor={})
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                amountAdded = 0 # How much to add to coverage count

                # Check if function got executed
                if bsonobj["count"] != 0:
                    amountAdded = 1 
   
                # Check if there exists an entry for this file
                if bsonobj["_id"]["file"] in results:
               
                    # Check if there exists function coverage data
                    if "funcCovCount" in results[bsonobj["_id"]["file"]]:
                        results[bsonobj["_id"]["file"]]["funcCovCount"]+= amountAdded
                        results[bsonobj["_id"]["file"]]["funcCount"] += 1

                    # Otherwise, initialize function coverage values
                    else:
                        results[bsonobj["_id"]["file"]]["funcCovCount"] = amountAdded
                        results[bsonobj["_id"]["file"]]["funcCount"] = 1

                # Otherwise, create a new entry
                else:
                    results[bsonobj["_id"]["file"]] = {}
                    results[bsonobj["_id"]["file"]]["funcCovCount"] = amountAdded
                    results[bsonobj["_id"]["file"]]["funcCount"] = 1

            # Add line and function coverage percentage data
            for key in results.keys():
                if "lineCount" in results[key]:
                    results[key]["lineCovPercentage"] = round(float(results[key]["lineCovCount"])/results[key]["lineCount"] * 100, 2)
                if "funcCount" in results[key]:
                    results[key]["funcCovPercentage"] = round(float(results[key]["funcCovCount"])/results[key]["funcCount"] * 100, 2)

            self.render("templates/data.html", results=results, url=url, directory=directory, gitHash=gitHash, buildID=buildID)

        else:
            gitHash = args.get("gitHash")[0]
            buildID = args.get("buildID")[0]
            fileName = args.get("file")[0]

            if "testName" in args:
                testName = args.get("testName")
                pipeline = [{"$match":{"file": fileName, "gitHash": gitHash, "buildID": buildID, "testName": testName}}, {"$project":{"file":1, "lc":1}}, {"$unwind": "$lc"}, {"$group":{"_id": {"file": "$file", "line": "$lc.ln"}, "count":{"$sum": "$lc.ec"}}}]
   
            else:
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


class MetaHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        self.json_args = json_decode(self.request.body)
        
        # Generate line count results
        gitHash = self.json_args["_id"]["gitHash"]
        buildID = self.json_args["_id"]["buildID"]
        self.write(gitHash + ", " + buildID)
        # Add option to specify what pattern to start with
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

        self.json_args["lineCount"] = total
        self.json_args["lineCovCount"] = total-noexecTotal
        self.json_args["lineCovPercentage"] = round(float(total-noexecTotal)/total * 100, 2)


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

        self.json_args["funcCount"] = total
        self.json_args["funcCovCount"] = total-noexec
        self.json_args["funcCovPercentage"] = round(float(total-noexec)/total * 100, 2)
  
        # Insert meta-information
        try:
            result = yield self.application.metaCollection.insert(self.json_args)
        except tornado.httpclient.HTTPError as e:
            print "Error:", e

        # Generate coverage data by directory
        pipelines.line_pipeline[0]["$match"]["gitHash"] = self.json_args["_id"]["gitHash"]
        pipelines.function_pipeline[0]["$match"]["gitHash"] = self.json_args["_id"]["gitHash"]
        pipelines.line_pipeline[0]["$match"]["buildID"] = self.json_args["_id"]["buildID"]
        pipelines.function_pipeline[0]["$match"]["buildID"] = self.json_args["_id"]["buildID"]

        cursor =  yield self.application.collection.aggregate(pipelines.line_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            
            # Generate line coverage percentage
            lineCount = bsonobj["lineCount"]
            lineCovCount = bsonobj["lineCovCount"]
            bsonobj["lineCovPercentage"] = round(float(lineCovCount)/lineCount * 100, 2)
            result = yield self.application.covCollection.insert(bsonobj)
        
        cursor =  yield self.application.collection.aggregate(pipelines.function_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()

            # Generate function coverage percentage
            funcCount = bsonobj["funcCount"]
            funcCovCount = bsonobj["funcCovCount"]
            funcCovPercentage = round(float(funcCovCount)/funcCount * 100, 2)
            result = yield self.application.covCollection.update({"_id": bsonobj["_id"]}, {"$set": {"funcCount": bsonobj["funcCount"], "funcCovCount": bsonobj["funcCovCount"], "funcCovPercentage": funcCovPercentage}})


class ReportHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments
        url = self.request.full_url()

        if len(args) == 0:
            # Get git hashes and build IDs 
            cursor =  self.application.metaCollection.find()
            results = []

            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                results.append(bsonobj)

            self.render("templates/report.html", results=results, url=url)
        else:    
            if args.get("gitHash") == None or args.get("buildID") == None:
                self.write("Error!\n")
                return
            url = self.request.full_url()[:-len(self.request.uri)]
            url += "/data"
            gitHash = args.get("gitHash")[0]
            buildID = args.get("buildID")[0]
            query = {"_id": {"gitHash": gitHash, "buildID": buildID}}
            cursor = self.application.metaCollection.find(query)
            metaResult = None
            dirResults = []
            
            # Get summary results
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                metaResult = bsonobj
           
            query = {"_id.gitHash": gitHash, "_id.buildID": buildID}
            cursor = self.application.covCollection.find(query)
            
            # Get directory results
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                dirResults.append(bsonobj)
            self.render("templates/directory.html", result=metaResult, dirResults=dirResults, url=url)



if __name__ == "__main__":
    application = Application()
    application.listen(application.httpport)
    tornado.ioloop.IOLoop.instance().start()

