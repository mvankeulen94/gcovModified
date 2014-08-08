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


import re

function_pipeline = [
	{
		"$project" : {
			"file" : 1,
			"git_hash" : 1,
			"build_id" : 1,
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
				"git_hash" : "$git_hash",
				"build_id" : "$build_id",
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
				"git_hash" : "$_id.git_hash",
				"build_id" : "$_id.build_id",
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
				"git_hash" : "$_id.git_hash",
				"build_id" : "$_id.build_id"
			},
			"func_count" : {
				"$sum" : 1
			},
			"func_cov_count" : {
				"$sum" : "$hit"
			}
		}
	}
]

line_pipeline = [
	{
		"$project" : {
			"file" : 1,
			"git_hash" : 1,
			"build_id" : 1,
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
				"git_hash" : "$git_hash",
				"build_id" : "$build_id",
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
				"git_hash" : "$_id.git_hash",
				"build_id" : "$_id.build_id",
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
				"git_hash" : "$_id.git_hash",
				"build_id" : "$_id.build_id"
			},
			"line_count" : {
				"$sum" : 1
			},
			"line_cov_count" : {
				"$sum" : "$hit"
			}
		}
	}
]

file_line_pipeline = [
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
		"$project" : {
			"build_id" : 1,
			"git_hash" : 1,
			"test_name" : 1
		}
	},
	{
		"$group" : {
			"_id" : {
				"git_hash" : "$git_hash",
				"build_id" : "$build_id"
			},
			"test_names" : {
				"$addToSet" : "$test_name"
			}
		}
	}
]

