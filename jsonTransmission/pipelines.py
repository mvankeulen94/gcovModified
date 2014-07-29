import re

function_pipeline = [
	{
		"$match" : {
			"buildID" : "",
			"gitHash" : "",
			"file" : re.compile("^src\/mongo") 
		}
	},
	{
		"$project" : {
			"file" : 1,
			"gitHash" : 1,
			"buildID" : 1,
			"dir" : 1,
			"functions" : 1
		}
	},
	{
		"$unwind" : "$functions"
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$file",
				"gitHash" : "$gitHash",
				"buildID" : "$buildID",
				"line" : "$functions.ln",
				"dir" : "$dir"
			},
			"count" : {
				"$sum" : "$functions.ec"
			}
		}
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$_id.file",
				"gitHash" : "$_id.gitHash",
				"buildID" : "$_id.buildID",
				"line" : "$_id.line",
				"dir" : "$_id.dir"
			},
			"hit" : {
				"$sum" : {
					"$cond" : {
						"if" : {
							"$eq" : [
								"$count",
								0
							]
						},
						"then" : 0,
						"else" : 1
					}
				}
			}
		}
	},
	{
		"$group" : {
			"_id" : {
				"dir" : "$_id.dir",
				"gitHash" : "$_id.gitHash",
				"buildID" : "$_id.buildID"
			},
			"funcCount" : {
				"$sum" : 1
			},
			"funcCovCount" : {
				"$sum" : "$hit"
			}
		}
	}
]

line_pipeline = [
	{
		"$match" : {
			"buildID" : "",
			"gitHash" : "",
			"file" : re.compile("^src\/mongo")
		}
	},
	{
		"$project" : {
			"file" : 1,
			"gitHash" : 1,
			"buildID" : 1,
			"dir" : 1,
			"lc" : 1
		}
	},
	{
		"$unwind" : "$lc"
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$file",
				"gitHash" : "$gitHash",
				"buildID" : "$buildID",
				"line" : "$lc.ln",
				"dir" : "$dir"
			},
			"count" : {
				"$sum" : "$lc.ec"
			}
		}
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$_id.file",
				"line" : "$_id.line",
				"gitHash" : "$_id.gitHash",
				"buildID" : "$_id.buildID",
				"dir" : "$_id.dir"
			},
			"hit" : {
				"$sum" : {
					"$cond" : {
						"if" : {
							"$eq" : [
								"$count",
								0
							]
						},
						"then" : 0,
						"else" : 1
					}
				}
			}
		}
	},
	{
		"$group" : {
			"_id" : {
				"dir" : "$_id.dir",
				"gitHash" : "$_id.gitHash",
				"buildID" : "$_id.buildID"
			},
			"lineCount" : {
				"$sum" : 1
			},
			"lineCovCount" : {
				"$sum" : "$hit"
			}
		}
	}
]

file_line_pipeline = [
	{
		"$match" : {
			"buildID" : "",
			"gitHash" : "",
			"file" : "" 
		}
	},
	{
		"$project" : {
			"file" : 1,
			"lc" : 1
		}
	},
	{
		"$unwind" : "$lc"
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$file",
				"line" : "$lc.ln"
			},
			"count" : {
				"$sum" : "$lc.ec"
			}
		}
	},
        {
                "$sort" : {
                        "_id.file": 1
                }
        }

]

file_func_pipeline = [
	{
		"$match" : {
			"buildID" : "",
			"gitHash" : "",
			"file" : "" 
		}
	},
	{
		"$project" : {
			"file" : 1,
			"functions" : 1
		}
	},
	{
		"$unwind" : "$functions"
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$file",
				"function" : "$functions.nm"
			},
			"count" : {
				"$sum" : "$functions.ec"
			}
		}
	},
        {
                "$sort" : {
                        "_id.file": 1
                }
        }

]

file_comp_pipeline = [
	{
		"$match" : {
			"buildID" : "",
			"dir" : "" 
		}
	},
	{
		"$project" : {
			"file" : 1,
			"lc" : 1
		}
	},
	{
		"$unwind" : "$lc"
	},
	{
		"$group" : {
			"_id" : {
				"file" : "$file",
				"line" : "$lc.ln"
			},
			"count" : {
				"$sum" : "$lc.ec"
			}
		}
	},
        {
                "$sort" : {
                        "_id.file": 1
                }
        }

]

testname_pipeline = [
	{
		"$match" : {
			"buildID" : "",
			"gitHash" : "",
			"file" : re.compile("^src\/mongo") 
		}
	},
	{
		"$project" : {
			"buildID" : 1,
			"gitHash" : 1,
			"testName" : 1
		}
	},
	{
		"$group" : {
			"_id" : {
				"gitHash" : "$gitHash",
				"buildID" : "$buildID"
			},
			"testNames" : {
				"$addToSet" : "$testName"
			}
		}
	}
]
