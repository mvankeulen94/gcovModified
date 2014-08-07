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
            (r"/", tornado.web.RedirectHandler, {"url": "/report"}),
        ],)

    # TODO: move to outside Application class
    @gen.coroutine
    def getMetaDocument(self, build_id, git_hash=None):
        """Retrieve meta document for build_id (and git hash)."""
        query = {"_id.build_id": build_id}
        
        # Add git hash if applicable
        if git_hash:
            query["_id.git_hash"] = git_hash 

        doc = yield self.metaCollection.find_one(query)
        raise gen.Return(doc)

    def requestGitHubFile(self, git_hash, file_name):
        """Retrieve file from GitHub with git_hash and file_name.
    
        Return highlighted file content and line count of content.
        """
        owner = "mongodb"
        repo = "mongo"
        token = self.token
        url = ("https://api.github.com/repos/" + owner + "/" + repo + 
               "/contents/" + file_name + "?ref=" + git_hash)
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
            self.write_error(422)


class DataHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def getDirectoryResults(self, results, specifier, git_hash, build_id, directory, test_name=None):
        """Retrieve coverage data for directories.

        results - dictionary in which results are stored
        specifier - e.g. "line" or "func"
        git_hash - git hash for which to obtain data
        build_id - build for which to obtain data
        directory - directory for which to obtain data
        test_name (optional) - test name for which to obtain data
        """
        match = {"$match": {"build_id": build_id, "git_hash": git_hash}}

        if test_name:
            match["$match"]["test_name"] = test_name 

        match["$match"]["file"] = re.compile("^" + directory)

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
        git_hash = urllib.unquote(args.get("git_hash")[0])
        build_id = urllib.unquote(args.get("build_id")[0])
        # Get meta document 
        doc = yield self.application.getMetaDocument(build_id, git_hash=git_hash)

        if not doc:
            self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash"]})
            return

        # Get branch name
        branch = doc["branch"]

        # Gather additional info to be passed to template
        additionalInfo = {"git_hash": git_hash, 
                          "build_id": build_id, 
                          "branch": branch}

        if "dir" in args or "test_name" in args and "dir" in args:

            directory = urllib.unquote(args.get("dir")[0])
            additionalInfo["directory"] = directory
            additionalInfo["clip"] = len(directory)

            # Get line results
            results = {} # Store coverage data

            if "test_name" in args:
                test_name = urllib.unquote(args.get("test_name")[0])
                yield self.getDirectoryResults(results, "line", git_hash, build_id, directory, test_name=test_name)
                yield self.getDirectoryResults(results, "func", git_hash, build_id, directory, test_name=test_name)
                additionalInfo["test_name"] = test_name
           
            else:
                yield self.getDirectoryResults(results, "line", git_hash, build_id, directory)
                yield self.getDirectoryResults(results, "func", git_hash, build_id, directory)

            if not results:
                self.render("templates/error.html", 
                            additionalInfo={"errorSources": ["Git hash", "Build ID", 
                                                             "Directory", "Test name"]})
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
            file_name = urllib.unquote(args.get("file")[0])

            additionalInfo["file_name"] = file_name
            
            if "test_name" in args:
                test_name = urllib.unquote(args.get("test_name")[0])
                additionalInfo["test_name"] = test_name
            
            # If coverage data is needed, do aggregation
            if "counts" in args and args["counts"][0] == "true":
                # Send only counts data to client
                if "test_name" in args:
                    file_line_pipeline = copy.copy(pipelines.file_line_pipeline)
                    match = {"$match": {"build_id": build_id, "git_hash": git_hash, 
                                        "test_name": test_name, "file": file_name}}
                    file_line_pipeline.insert(0, match)
       
                else:
                    # Fill pipeline with git_hash, build_id, and file_name info
                    file_line_pipeline = copy.copy(pipelines.file_line_pipeline)
                    match = {"$match": {"build_id": build_id, "git_hash": git_hash, "file": file_name}}
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
                file_name = urllib.unquote(args["file"][0])
                (content, lineCount) = self.application.requestGitHubFile(git_hash, file_name)

                if content == "None":
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash", "File name"]})
                    return
                
                # Add syntax highlighting
                fileContent = self.application.add_syntax_highlighting(content)
                # Get meta document 
                doc = yield self.application.getMetaDocument(build_id, git_hash=git_hash)

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
        if not ("git_hash" in json_args["_id"] and 
                "build_id" in json_args["_id"]):
            self.write_error(422)
            return

        # Generate line count results
        git_hash = json_args["_id"]["git_hash"]
        build_id = json_args["_id"]["build_id"]
        self.write(git_hash + ", " + build_id)
        # Add option to specify what pattern to start with
        pipeline = [{"$match":{"build_id": build_id, "git_hash": git_hash,
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
            total += bsonobj["count"] 
            noexecTotal += bsonobj["noexec"] 

        json_args["lineCount"] = total
        json_args["lineCovCount"] = total-noexecTotal
        json_args["lineCovPercentage"] = round(float(total-noexecTotal)/total * 100, 2)

        # Generate function results
        pipeline = [{"$project": {"file":1,"functions":1}}, {"$unwind":"$functions"},
                    {"$group": { "_id":"$functions.nm", 
                                 "count" : { "$sum" : "$functions.ec"}}}] 
        cursor =  yield self.application.collection.aggregate(pipeline, cursor={})
        noexecTotal = 0
        total = 0
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            total += 1
            if bsonobj["count"] == 0:
                noexecTotal += 1

        json_args["funcCount"] = total
        json_args["funcCovCount"] = total-noexecTotal
        json_args["funcCovPercentage"] = round(float(total-noexecTotal)/total * 100, 2)

        # Retrieve test name list
        match = {"$match": {"build_id": build_id, "git_hash": git_hash}}
        testname_pipeline = copy.copy(pipelines.testname_pipeline)
        testname_pipeline.insert(0, match)
        cursor =  yield self.application.collection.aggregate(testname_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            json_args["test_names"] = bsonobj["test_names"]
        
        json_args["date"] = datetime.datetime.strptime(json_args["date"], "%Y-%m-%dT%H:%M:%S.%f")

        # Insert meta-information
        try:
            result = yield self.application.metaCollection.update({"_id.build_id": build_id, "_id.git_hash": git_hash}, json_args, upsert=True)
        except tornado.httpclient.HTTPError as e:
            self.write_error(422)
            return

        # Generate coverage data by directory
        line_pipeline = copy.copy(pipelines.line_pipeline)
        function_pipeline = copy.copy(pipelines.function_pipeline)

        match = {"$match": {"build_id": json_args["_id"]["build_id"], "git_hash": json_args["_id"]["git_hash"],
                            "file": re.compile("^src\/mongo")}}

        line_pipeline.insert(0, match)
        function_pipeline.insert(0, match)

        cursor = yield self.application.collection.aggregate(line_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()
            
            # Generate line coverage percentage
            lineCount = bsonobj["lineCount"]
            lineCovCount = bsonobj["lineCovCount"]
            bsonobj["lineCovPercentage"] = round(float(lineCovCount)/lineCount * 100, 2)
            query = {"_id.build_id": build_id, "_id.git_hash": git_hash, 
                     "_id.dir": bsonobj["_id"]["dir"]}
            result = yield self.application.covCollection.update(query, bsonobj, upsert=True)
        
        cursor =  yield self.application.collection.aggregate(function_pipeline, cursor={})
        while (yield cursor.fetch_next):
            bsonobj = cursor.next_object()

            # Generate function coverage percentage
            funcCount = bsonobj["funcCount"]
            funcCovCount = bsonobj["funcCovCount"]
            funcCovPercentage = round(float(funcCovCount)/funcCount * 100, 2)
            query = {"_id": bsonobj["_id"]}
            modification = {"$set": {"funcCount": bsonobj["funcCount"], 
                                     "funcCovCount": bsonobj["funcCovCount"], 
                                     "funcCovPercentage": funcCovPercentage}}
            result = yield self.application.covCollection.update(query, modification)


class ReportHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def getBuildGitHashResults(self, results, specifier, git_hash, build_id, test_name=None):
        """Retreieve coverage data for directories.

        results - dictionary in which results are stored
        specifier - e.g. "line" or "func"
        git_hash - git hash for which to obtain data
        build_id - build for which to obtain data
        test_name (optional) - test name for which to obtain data
        """
        match = {"$match": {"build_id": build_id, "git_hash": git_hash,
                            "file": re.compile("^src\/mongo")}}

        if test_name:
            match["$match"]["test_name"] = test_name 
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
                query = {"_id.build_id": build_id, "_id.git_hash": git_hash}
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
                query = {"_id.build_id": build_id, "_id.git_hash": git_hash}
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
            if args.get("git_hash") == None or args.get("build_id") == None:
                self.render("templates/error.html", additionalInfo={"errorSources": ["Git hash", "Build ID"]})
                return

            git_hash = urllib.unquote(args.get("git_hash")[0])
            build_id = urllib.unquote(args.get("build_id")[0])
            results = {}
            clip=len("src/mongo/")

            # Get meta document 
            doc = yield self.application.getMetaDocument(build_id, git_hash=git_hash)
    
            if not doc:
                self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID", "Git hash"]})
                return

            # Get branch name
            branch = doc["branch"]

            # Get test names
            test_names = doc["test_names"]
            additionalInfo = {"git_hash": git_hash, "build_id": build_id,
                              "branch": branch, "test_names": test_names, 
                              "clip": clip}
            
            if "test_name" in args and urllib.unquote(args["test_name"][0]) != "All tests":
                test_name = urllib.unquote(args.get("test_name")[0])
                additionalInfo["test_name"] = test_name
                yield self.getBuildGitHashResults(results, "line", git_hash, build_id, test_name=test_name)
                yield self.getBuildGitHashResults(results, "func", git_hash, build_id, test_name=test_name)

            else:
                yield self.getBuildGitHashResults(results, "line", git_hash, build_id)
                yield self.getBuildGitHashResults(results, "func", git_hash, build_id)

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

        if "build_id1" in args:
            if not "build_id2" in args:
                return

            build_ids = [urllib.unquote(args["build_id1"][0]), urllib.unquote(args["build_id2"][0])]
            build_id1 = build_ids[0]
            build_id2 = build_ids[1]

            # Directory comparison
            if "dir" in args:
                results = {}
                directory = urllib.unquote(args.get("dir")[0])

                # Get coverage comparison data
                yield self.getComparisonData(results, build_ids, directory=directory)

                if not results:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 1", "Build ID 2", "Directory"]})
                    return

                self.addCoverageComparison(results)

                self.render("templates/dirCompare.html", build_id1=build_id1, build_id2=build_id2, results=results, directory=directory)
            
            # File comparison
            elif "file" in args:
                build_id1 = args["build_id1"][0] 
                build_id2 = args["build_id2"][0]

                # Retrieve git hashes
                doc = yield self.application.getMetaDocument(build_id1)
                if not doc:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 1", "Build ID 2"]})
                    return
                git_hash1 = doc["_id"]["git_hash"]

                doc = yield self.application.getMetaDocument(build_id2)
                if not doc:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 2"]})
                    return
                git_hash2 = doc["_id"]["git_hash"]

                file_name = urllib.unquote(args.get("file")[0])

                # Request GitHub files
                content1, lineCount1 = self.application.requestGitHubFile(git_hash1, file_name)
                content2, lineCount2 = self.application.requestGitHubFile(git_hash2, file_name)
                # Add syntax highlighting
                fileContent1 = self.application.add_syntax_highlighting(content1, identifier="A")
                fileContent2 = self.application.add_syntax_highlighting(content2, identifier="B")

                self.render("templates/fileCompare.html", build_id1=build_id1, build_id2=build_id2, fileContent1=fileContent1, fileContent2=fileContent2, file_name=file_name, git_hash1=git_hash1, git_hash2=git_hash2, lineCount1=lineCount1, lineCount2=lineCount2)
           
            # Build comparison
            else:
                results = {}
                # Get coverage comparison data
                yield self.getComparisonData(results, build_ids)

                if not results:
                    self.render("templates/error.html", additionalInfo={"errorSources": ["Build ID 1", "Build ID 2"]})
                    return

                self.addCoverageComparison(results)
    
                self.render("templates/buildCompare.html", build_id1=build_id1, 
                            build_id2=build_id2, results=results)
    
    @gen.coroutine            
    def getComparisonData(self, results, build_ids, directory=None):           
        """Get coverage comparison data for build_ids."""
        for i in range(len(build_ids)):

            if directory: 
                # Fill pipeline with build/directory info
                match = {"$match": {"build_id": build_ids[i], "dir": directory}}
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
                query = {"_id.build_id": build_ids[i]}
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
