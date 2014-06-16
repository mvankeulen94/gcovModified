import sys

def main():
    """Read a JSON file and output the file with added values.

    gitHash and version, which are passed as command line arguments,
    are added to the JSON that is output.
    """

    if len(sys.argv) < 3:
        print "Too few arguments."
        sys.exit(1)
  
    filename = raw_input("Please enter file name: ")
    f = open(filename, "r")

    for line in f:
        gitHash = "\"gitHash\": " + sys.argv[1] + ", "
        version = "\"version\": " + sys.argv[2] + ", "
        line = "{" + gitHash + version + line[line.index('{')+1:]
        print line

    f.close() 

main()
