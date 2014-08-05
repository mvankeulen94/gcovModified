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

# TODO: reorder imports
# TODO: fix variable naming conventions
import pymongo
import json
from bson.json_util import dumps as bsondumps
import re

import datetime

import tornado.ioloop
import tornado.web
from tornado.escape import json_decode
import motor
from tornado import gen
import ssl
import tornado.httpclient
import base64

from pygments import highlight
from pygments.lexers import CppLexer
from pygments.formatters import HtmlFormatter

import pipelines

import urllib
import string
import copy


class Application(tornado.web.Application):
    def __init__(self):
        with open("config.conf", "r") as f:
            conf = json.loads(f.readline())
        self.client = motor.MotorClient(host=conf["hostname"], port=conf["port"], 
                                        ssl=True, ssl_certfile=conf["client_pem"], 
                                        ssl_cert_reqs=ssl.CERT_REQUIRED, 
                                        ssl_ca_certs=conf["ca_file"])

        self.client.the_database.authenticate(conf["username"], mechanism="MONGODB-X509")

        self.db = self.client[conf["database"]]
        self.collection = self.db[conf["collection"]]
        self.metaCollection = self.db[conf["metaCollection"]]
        self.covCollection = self.db[conf["covCollection"]]
        self.httpport = conf["httpport"]
        self.token = conf["github_token"]
       
        super(Application, self).__init__([
            (r"/", MainHandler),
            (r"/report", ReportHandler),
            (r"/data", DataHandler),
            (r"/meta", CacheHandler),
            (r"/style", StyleHandler),
            (r"/compare", CompareHandler),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static/"}),
        ],)

    # TODO: move to outside Application class
    @gen.coroutine
    def getMetaDocument(self, buildID, gitHash=None):
        """Retrieve meta document for buildID (and git hash)."""
        query = {"_id.buildID": buildID}
        
        # Add git hash if applicable
        if gitHash:
            query["_id.gitHash"] = gitHash 

        doc = yield self.metaCollection.find_one(query)
        raise gen.Return(doc)

    def requestGitHubFile(self, gitHash, fileName):
        """Retrieve file from GitHub with gitHash and fileName.
    
        Return highlighted file content and line count of content.
        """
        owner = "mongodb"
        repo = "mongo"
        token = self.token
        url = ("https://api.github.com/repos/" + owner + "/" + repo + 
               "/contents/" + fileName + "?ref=" + gitHash)
        headers = {"Authorization": "token " + token}
        http_client = tornado.httpclient.HTTPClient()
        request = tornado.httpclient.HTTPRequest(url=url, headers=headers,
                                                 user_agent="Maria's API Test")
        try:
            response = http_client.fetch(request)
            responseDict = json.loads(response.body)
            content = base64.b64decode(responseDict["content"])
            lineCount = content.count("\n")
    
        except tornado.httpclient.HTTPError:
            content = "None"
            lineCount = 0
        
        http_client.close()
        return content, lineCount

    def add_syntax_highlighting(self, content, identifier=""):
        """Add syntax highlighting to content, using identifier."""
        fileContent = highlight(content, CppLexer(), CoverageFormatter(identifier))
        return fileContent

    
class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        # TODO: GET method with appropriate redirect for user friendliness?
        # redirect to /report home page
        if self.request.headers.get("Content-Type") == "application/json":
            json_args = json_decode(self.request.body)
      
            # Insert information
            result = yield self.application.collection.insert(json_args)
            self.write("\nRecord for " + json_args.get("file") + 
                       " inserted!\n")
        else:
            self.write_error("\n422: Unprocessable Entity\n")


class DataHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def getDirectoryResults(self, results, specifier, gitHash, buildID, **kwargs):
        """Retrieve coverage data for directories.

        results - dictionary in which results are stored
        specifier - e.g. "line" or "func"
        gitHash - git hash for which to obtain data
        buildID - build for which to obtain data
        kwargs - place to specify test name and/or directory
        """
        match = {"$match": {"buildID": buildID, "gitHash": gitHash}}

        if "testName" in kwargs:
            match["$match"]["testName"] = kwargs["testName"]

        if "directory" in kwargs:
            match["$match"]["file"] = re.compile("^" + kwargs["directory"])

        else:
            match["$match"]["file"] = re.compile("^src\/mongo")

        if specifier == "line":
            pipeline = copy.copy(pipelines.file_line_pipeline)
            count_key = "lineCount"
            cov_count_key = "lineCovCount"

        else:
            pipeline = copy.copy(pipelines.file_func_pipeline)
            count_key = "funcCount"
            cov_count_key = "funcCovCount"

        pipeline.insert(0, match)

        # Get line results
        cursor = yield self.application.collection.aggregate(pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            amountAdded = 0
            if bsonobj["count"] != 0:
                amountAdded = 1

            # Check if there exists an entry for this file
            key = bsonobj["_id"]["file"]
            if key in results:

                if count_key in results[key]:
                    results[key][cov_count_key]+= amountAdded
                    results[key][count_key] += 1

                else:
                    results[key][cov_count_key] = amountAdded
                    results[key][count_key] = 1

            # Otherwise, create a new entry
            else:
                results[key] = {}
                results[key][cov_count_key] = amountAdded
                results[key][count_key] = 1

        raise gen.Return(results)

    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments
        if len(args) == 0:
            self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash", "Directory"]})
            return

        query = {}
        cursor = None # Cursor with which to traverse query results
        result = None # Dictionary to store query result
        gitHash = urllib.unquote(args.get("gitHash")[0])
        buildID = urllib.unquote(args.get("buildID")[0])
        # Get meta document 
        doc = yield self.application.getMetaDocument(buildID, gitHash=gitHash)

        if not doc:
            self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash"]})
            return

        # Get branch name
        branch = doc["branch"]

        # Gather additional info to be passed to template
        additionalInfo = {"gitHash": gitHash, 
                          "buildID": buildID, 
                          "branch": branch}

        if "dir" in args or "testName" in args and "dir" in args:

            directory = urllib.unquote(args.get("dir")[0])
            additionalInfo["directory"] = directory
            additionalInfo["clip"] = len(directory)

            # Get line results
            results = {} # Store coverage data

            if "testName" in args:
                testName = urllib.unquote(args.get("testName")[0])
                results = yield self.getDirectoryResults(results, "line", gitHash, buildID, directory=directory, testName=testName)
                results = yield self.getDirectoryResults(results, "func", gitHash, buildID, directory=directory, testName=testName)
                additionalInfo["testName"] = testName
           
            else:
                results = yield self.getDirectoryResults(results, "line", gitHash, buildID, directory=directory)
                results = yield self.getDirectoryResults(results, "func", gitHash, buildID, directory=directory)

            if not results:
                self.render("templates/error.html", additionalInfo={"errorSources": ["Git hash", "Build ID", "Directory", "Test name"]})
                return

            # Add line and function coverage percentage data
            for key in results.keys():
                if "lineCount" in results[key]:
                    results[key]["lineCovPercentage"] = round(float(results[key]["lineCovCount"])/results[key]["lineCount"] * 100, 2)
                if "funcCount" in results[key]:
                    results[key]["funcCovPercentage"] = round(float(results[key]["funcCovCount"])/results[key]["funcCount"] * 100, 2)

            self.render("templates/data.html", results=results, additionalInfo=additionalInfo)

        else:
            if not "file" in args:
                self.render("templates/error.html", additionalInfo={"errorSources": ["File name"]})
                return
            
            # Generate line coverage results
            gitHash = urllib.unquote(args.get("gitHash")[0])
            buildID = urllib.unquote(args.get("buildID")[0])
            fileName = urllib.unquote(args.get("file")[0])

            additionalInfo = {"buildID": buildID, "gitHash": gitHash,
                              "fileName": fileName}            
            
            if "testName" in args:
                testName = urllib.unquote(args.get("testName")[0])
                additionalInfo["testName"] = testName
            
            # If coverage data is needed, do aggregation
            if "counts" in args and args["counts"][0] == "true":
                # Send only counts data to client
                if "testName" in args:
                    file_line_pipeline = copy.copy(pipelines.file_line_pipeline)
                    match = {"$match": {"buildID": buildID, "gitHash": gitHash, 
                                        "testName": testName, "file": fileName}}
                    file_line_pipeline.insert(0, match)
       
                else:
                    # Fill pipeline with gitHash, buildID, and fileName info
                    file_line_pipeline = copy.copy(pipelines.file_line_pipeline)
                    match = {"$match": {"buildID": buildID, "gitHash": gitHash, "file": fileName}}
                    file_line_pipeline.insert(0, match)
    
                cursor =  yield self.application.collection.aggregate(file_line_pipeline, cursor={})
                result = {}
                result["counts"] = {}
                while (yield cursor.fetch_next):
                    bsonobj = cursor.next_object()
                    key = bsonobj["_id"]["line"]
                    if not "file" in result:
                        result["file"] = bsonobj["_id"]["file"]
                    if not key in result["counts"]:
                        result["counts"][key] = bsonobj["count"] 
                    else:
                        result["counts"][key] += bsonobj["count"]
                
                if not result["counts"]:
                    self.write(json.dumps({"result": "None"}))
                    return

                self.write(json.dumps(result))

            # Otherwise, obtain file content from github
            else: 
                # Request file from github
                fileName = urllib.unquote(args["file"][0])
                (content, lineCount) = self.application.requestGitHubFile(gitHash, fileName)

                if content == "None":
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash", "File name"]})
                    return
                
                # Add syntax highlighting
                fileContent = self.application.add_syntax_highlighting(content)
                # Get meta document 
                doc = yield self.application.getMetaDocument(buildID, gitHash=gitHash)

                if not doc:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash"]})
                    return

                # Get branch name
                branch = doc["branch"]
                additionalInfo["branch"] = branch

                additionalInfo["fileContent"] = fileContent
                additionalInfo["lineCount"] = lineCount
                self.render("templates/file.html", additionalInfo=additionalInfo)


class CacheHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        json_args = json_decode(self.request.body)
        if not ("gitHash" in json_args["_id"] and 
                "buildID" in json_args["_id"]):
            self.write("Error!\n")
            return

        # Generate line count results
        gitHash = json_args["_id"]["gitHash"]
        buildID = json_args["_id"]["buildID"]
        self.write(gitHash + ", " + buildID)
        # Add option to specify what pattern to start with
        pipeline = [{"$match":{"buildID": buildID, "gitHash": gitHash,
                               "file": re.compile("^src\/mongo")}}, 
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

        json_args["lineCount"] = total
        json_args["lineCovCount"] = total-noexecTotal
        json_args["lineCovPercentage"] = round(float(total-noexecTotal)/total * 100, 2)

        # Generate function results
        pipeline = [{"$project": {"file":1,"functions":1}}, {"$unwind":"$functions"},
                    {"$group": { "_id":"$functions.nm", 
                                 "count" : { "$sum" : "$functions.ec"}}}] 
        cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
        noexec = 0
        total = 0
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            count = bsonobj["count"]
            total += 1
            if count == 0:
                noexec += 1

        json_args["funcCount"] = total
        json_args["funcCovCount"] = total-noexec
        json_args["funcCovPercentage"] = round(float(total-noexec)/total * 100, 2)

        # Retrieve test name list
        match = {"$match": {"buildID": buildID, "gitHash": gitHash}}
        testname_pipeline = copy.copy(pipelines.testname_pipeline)
        testname_pipeline.insert(0, match)
        cursor =  yield self.application.collection.aggregate(testname_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            json_args["testNames"] = bsonobj["testNames"]
        
        json_args["date"] = datetime.datetime.strptime(json_args["date"], "%Y-%m-%dT%H:%M:%S.%f")

        # Insert meta-information
        try:
            result = yield self.application.metaCollection.update({"_id.buildID": buildID, "_id.gitHash": gitHash}, json_args, upsert=True)
        except tornado.httpclient.HTTPError as e:
            print "Error:", e

        # Generate coverage data by directory
        line_pipeline = copy.copy(pipelines.line_pipeline)
        function_pipeline = copy.copy(pipelines.function_pipeline)

        match = {"$match": {"buildID": json_args["_id"]["buildID"], "gitHash": json_args["_id"]["gitHash"],
                            "file": re.compile("^src\/mongo")}}

        line_pipeline.insert(0, match)
        function_pipeline.insert(0, match)

        cursor =  yield self.application.collection.aggregate(line_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            
            # Generate line coverage percentage
            lineCount = bsonobj["lineCount"]
            lineCovCount = bsonobj["lineCovCount"]
            bsonobj["lineCovPercentage"] = round(float(lineCovCount)/lineCount * 100, 2)
            result = yield self.application.covCollection.update({"_id.buildID": buildID, "_id.gitHash": gitHash, "_id.dir": bsonobj["_id"]["dir"]}, bsonobj, upsert=True)
        
        cursor =  yield self.application.collection.aggregate(function_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()

            # Generate function coverage percentage
            funcCount = bsonobj["funcCount"]
            funcCovCount = bsonobj["funcCovCount"]
            funcCovPercentage = round(float(funcCovCount)/funcCount * 100, 2)
            result = yield self.application.covCollection.update({"_id": bsonobj["_id"]}, {"$set": {"funcCount": bsonobj["funcCount"], "funcCovCount": bsonobj["funcCovCount"], "funcCovPercentage": funcCovPercentage}})


class ReportHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def getBuildGitHashResults(self, results, specifier, gitHash, buildID, **kwargs):
        """Retreieve coverage data for directories.

        results - dictionary in which results are stored
        specifier - e.g. "line" or "func"
        gitHash - git hash for which to obtain data
        buildID - build for which to obtain data
        kwargs - place to specify test name
        """
        match = {"$match": {"buildID": buildID, "gitHash": gitHash,
                            "file": re.compile("^src\/mongo")}}

        if "testName" in kwargs:
            match["$match"]["testName"] = kwargs["testName"]
            action = "aggregate"
        else:
            action = "query"

        # Generate coverage data by directory
        if specifier == "line":
            if action == "aggregate":
                line_pipeline = copy.copy(pipelines.line_pipeline)
                line_pipeline.insert(0, match)
                cursor =  yield self.application.collection.aggregate(line_pipeline, cursor={})
            else:
                query = {"_id.buildID": buildID, "_id.gitHash": gitHash}
                cursor = self.application.covCollection.find(query).sort("_id.dir", pymongo.ASCENDING)

            # Get directory results
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()

                if not bsonobj["_id"]["dir"] in results:
                    results[bsonobj["_id"]["dir"]] = {}
                
                # Add line count data
                lineCount = bsonobj["lineCount"]
                lineCovCount = bsonobj["lineCovCount"]
                results[bsonobj["_id"]["dir"]]["lineCount"] = lineCount 
                results[bsonobj["_id"]["dir"]]["lineCovCount"] = lineCovCount 
                results[bsonobj["_id"]["dir"]]["lineCovPercentage"] = round(float(lineCovCount)/lineCount * 100, 2)

        else:
            if action == "aggregate":
                function_pipeline = copy.copy(pipelines.function_pipeline)
                function_pipeline.insert(0, match)
                cursor =  yield self.application.collection.aggregate(function_pipeline, cursor={})

            else:
                query = {"_id.buildID": buildID, "_id.gitHash": gitHash}
                cursor = self.application.covCollection.find(query).sort("_id.dir", pymongo.ASCENDING)

            # Get directory results
            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()

                if not bsonobj["_id"]["dir"] in results:
                    results[bsonobj["_id"]["dir"]] = {}

               # Add function count data
                funcCount = bsonobj["funcCount"]
                funcCovCount = bsonobj["funcCovCount"]
                results[bsonobj["_id"]["dir"]]["funcCount"] = bsonobj["funcCount"]
                results[bsonobj["_id"]["dir"]]["funcCovCount"] = bsonobj["funcCovCount"]
                results[bsonobj["_id"]["dir"]]["funcCovPercentage"] = round(float(funcCovCount)/funcCount * 100, 2)

        raise gen.Return(results)

    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments

        if len(args) == 0:
            # Get git hashes and build IDs 
            cursor =  self.application.metaCollection.find().sort("date", pymongo.DESCENDING)
            results = []

            while (yield cursor.fetch_next):
                bsonobj = cursor.next_object()
                results.append(bsonobj)
            
            if not results:
                self.render("templates/error.html", additionalInfo={})
                return

            self.render("templates/report.html", results=results)

        else:    
            if args.get("gitHash") == None or args.get("buildID") == None:
                self.render("templates/error.html", additionalInfo={"errorSources": ["Git hash", "Build ID"]})
                return

            gitHash = urllib.unquote(args.get("gitHash")[0])
            buildID = urllib.unquote(args.get("buildID")[0])
            results = {}
            clip=len("src/mongo/")

            # Get meta document 
            doc = yield self.application.getMetaDocument(buildID, gitHash=gitHash)
    
            if not doc:
                self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash"]})
                return

            # Get branch name
            branch = doc["branch"]

            # Get test names
            testNames = doc["testNames"]
            additionalInfo = {"gitHash": gitHash, "buildID": buildID,
                              "branch": branch, "testNames": testNames, 
                              "clip": clip}
            
            if "testName" in args and urllib.unquote(args["testName"][0]) != "All tests":
                testName = urllib.unquote(args.get("testName")[0])
                additionalInfo["testName"] = testName
                results = yield self.getBuildGitHashResults(results, "line", gitHash, buildID, testName=testName)
                results = yield self.getBuildGitHashResults(results, "func", gitHash, buildID, testName=testName)

            else:
                results = yield self.getBuildGitHashResults(results, "line", gitHash, buildID)
                results = yield self.getBuildGitHashResults(results, "func", gitHash, buildID)

            if not results:
                self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash", "Test name"]})
                return

            self.render("templates/directory.html", 
                        dirResults=results, additionalInfo=additionalInfo)


class CoverageFormatter(HtmlFormatter):
    def __init__(self, identifier):
        HtmlFormatter.__init__(self, linenos="table")
        self.identifier = identifier
    
    def wrap(self, source, outfile):
        return self._wrap_code(source)

    def _wrap_code(self, source):
        num = 0
        yield 0, '<div class="highlight"><pre>'
        for i, t in source:
            if i == 1:
                num += 1
                t = ('<span id="line%s%s">' % 
                     (self.identifier, str(num)) + t)
                t += '</span>'
            yield i, t
        yield 0, '</pre></div>'


class CompareHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments 
        if len(args) == 0:
            return

        if "buildID1" in args:
            if not "buildID2" in args:
                return

            buildIDs = [urllib.unquote(args["buildID1"][0]), urllib.unquote(args["buildID2"][0])]
            buildID1 = buildIDs[0]
            buildID2 = buildIDs[1]

            # Directory comparison
            if "dir" in args:
                results = {}
                directory = urllib.unquote(args.get("dir")[0])

                # Get coverage comparison data
                results = yield self.getComparisonData(buildIDs, directory=directory)

                if not results:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 1", "Build ID 2", "Directory"]})
                    return

                self.addCoverageComparison(results)

                self.render("templates/dirCompare.html", buildID1=buildID1, buildID2=buildID2, results=results, directory=directory)
            
            # File comparison
            elif "file" in args:
                buildID1 = args["buildID1"][0] 
                buildID2 = args["buildID2"][0]

                # Retrieve git hashes
                doc = yield self.application.getMetaDocument(buildID1)
                if not doc:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 1", "Build ID 2"]})
                    return
                gitHash1 = doc["_id"]["gitHash"]

                doc = yield self.application.getMetaDocument(buildID2)
                if not doc:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 2"]})
                    return
                gitHash2 = doc["_id"]["gitHash"]

                fileName = urllib.unquote(args.get("file")[0])

                # Request GitHub files
                content1, lineCount1 = self.application.requestGitHubFile(gitHash1, fileName)
                content2, lineCount2 = self.application.requestGitHubFile(gitHash2, fileName)
                # Add syntax highlighting
                fileContent1 = self.application.add_syntax_highlighting(content1, identifier="A")
                fileContent2 = self.application.add_syntax_highlighting(content2, identifier="B")

                self.render("templates/fileCompare.html", buildID1=buildID1, buildID2=buildID2, fileContent1=fileContent1, fileContent2=fileContent2, fileName=fileName, gitHash1=gitHash1, gitHash2=gitHash2, lineCount1=lineCount1, lineCount2=lineCount2)
           
            # Build comparison
            else:
                # Get coverage comparison data
                results = yield self.getComparisonData(buildIDs)

                if not results:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 1", "Build ID 2"]})
                    return

                self.addCoverageComparison(results)
    
                self.render("templates/buildCompare.html", buildID1=buildID1, 
                            buildID2=buildID2, results=results)
    
    @gen.coroutine            
    def getComparisonData(self, buildIDs, **kwargs):           
        results = {} # Store coverage data
        for i in range(len(buildIDs)):

            if "directory" in kwargs:
                directory = kwargs["directory"]
                # Fill pipeline with build/directory info
                match = {"$match": {"buildID": buildIDs[i], "dir": directory}}
                file_comp_pipeline = copy.copy(pipelines.file_comp_pipeline)
                file_comp_pipeline.insert(0, match)
                cursor = yield self.application.collection.aggregate(file_comp_pipeline, cursor={})
    
                while (yield cursor.fetch_next):
                    bsonobj = cursor.next_object()
                    amountAdded = 0
                    if bsonobj["count"] != 0:
                        amountAdded = 1
                        
                    # Check if there exists an entry for this file
                    if bsonobj["_id"]["file"] in results:
                        if "lineCovCount" + str(i+1) in results[bsonobj["_id"]["file"]]:
                            results[bsonobj["_id"]["file"]]["lineCovCount" + str(i+1)]+= amountAdded
                            results[bsonobj["_id"]["file"]]["lineCount" + str(i+1)] += 1
                        else:
                            results[bsonobj["_id"]["file"]]["lineCovCount" + str(i+1)] = amountAdded
                            results[bsonobj["_id"]["file"]]["lineCount" + str(i+1)] = 1
                        
                    # Otherwise, create a new entry
                    else:
                        results[bsonobj["_id"]["file"]] = {}
                        results[bsonobj["_id"]["file"]]["lineCovCount" + str(i+1)] = amountAdded
                        results[bsonobj["_id"]["file"]]["lineCount" + str(i+1)] = 1
    
            else:
                query = {"_id.buildID": buildIDs[i]}
                cursor =  self.application.covCollection.find(query)

                while (yield cursor.fetch_next):
                    bsonobj = cursor.next_object()
                    if not bsonobj["_id"]["dir"] in results:
                        results[bsonobj["_id"]["dir"]] = {}
                    dirEntry = results[bsonobj["_id"]["dir"]]
                    dirEntry["lineCount" + str(i+1)] = bsonobj["lineCount"]
                    dirEntry["lineCovCount" + str(i+1)] = bsonobj["lineCovCount"]
                    dirEntry["lineCovPercentage" + str(i+1)] = bsonobj["lineCovPercentage"]

                    
            # Add line and function coverage percentage data
            for key in results.keys():
                if "lineCovCount" + str(i+1) in results[key]:
                    results[key]["lineCovPercentage" + str(i+1)] = round(float(results[key]["lineCovCount" + str(i+1)])/results[key]["lineCount" + str(i+1)] * 100, 2)
        raise gen.Return(results)


    def addCoverageComparison(self, results):
        """Add coverage comparison data to results."""
        for key in results.keys():
            entry = results[key]

            # Either lineCount1 or lineCount2 is missing
            if not ("lineCount1" in entry and "lineCount2" in entry):
                entry["highlight"] = "warning"
                if "lineCount1" in entry:
                    entry["coverageComparison"] = "?"
                    entry["lineCount2"] = "N/A"
                    entry["lineCovCount2"] = "N/A"
                    entry["lineCovPercentage2"] = "N/A"
                else:
                    entry["coverageComparison"] = "?"
                    entry["lineCount1"] = "N/A"
                    entry["lineCovCount1"] = "N/A"
                    entry["lineCovPercentage1"] = "N/A"
                continue
            
            # lineCount1 and lineCount2 are present; do comparison
            if entry["lineCovPercentage1"] != entry["lineCovPercentage2"]:
                if entry["lineCovPercentage1"] > entry["lineCovPercentage2"]:
                    entry["coverageComparison"] = "-" 
                    entry["highlight"] = "danger"
                else:
                    entry["coverageComparison"] = "+"
                    entry["highlight"] = "success"

            # The two percentages are equal
            else:
                if entry["lineCovPercentage1"] == 100:
                    entry["coverageComparison"] = " "

                # The two percentages are equal and not 100
                else:
                    if entry["lineCount1"] == entry["lineCount2"]:
                        entry["coverageComparison"] = " "
                    else:
                        entry["coverageComparison"] = "N"
                        entry["highlight"] = "warning"


class StyleHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        args = self.request.arguments
        if len(args) != 0:
            return
        self.write(CoverageFormatter("").get_style_defs(".highlight"))


if __name__ == "__main__":
    application = Application()
    application.listen(application.httpport)
    tornado.ioloop.IOLoop.instance().start()
