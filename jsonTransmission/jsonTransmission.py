import sys
import optparse
import pymongo
from pymongo import MongoClient
import json
from pprint import pprint

import tornado.ioloop
import tornado.web
from tornado.escape import json_decode
import motor

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

#main()

class MainHandler(tornado.web.RequestHandler):
#    conf = json.loads(open("config.conf", "r").readline())
#    print conf
    def get(self):
        self.write("Hello, world")
    def post(self):
        self.write(self.request.headers.get("Content-Type"))
        if self.request.headers.get("Content-Type") == "application/json":
            self.json_args = json_decode(self.request.body)
            collection.insert(self.json_args)
            funcList = self.json_args.get("functions")
            for func in funcList:
                self.write("Name: "+ func["nm"]+ "\n")
                # type issues with the following. Fixie
                #self.write("Line:"+ func["ln"]+ "<br>")
                #self.write("Exec Count:"+ func["ec"]+ "<br>")
        else:
            self.write("Error!")

if __name__ == "__main__":
    configFile = open("config.conf", "r")
    conf = json.loads(configFile.readline())
    configFile.close()
    client = motor.MotorClient(conf["hostname"], conf["port"])
    db = client[conf["database"]]
    collection = db[conf["collection"]]
    application = tornado.web.Application([
        (r"/", MainHandler),
    ], db=db)
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
