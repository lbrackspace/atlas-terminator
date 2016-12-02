#!/usr/bin/env python

import operator
import dateutil
import json
import sys
import os

from terminator.app import utils

feed_path = "./terminator/test/test.json"
feed_json = open(os.path.expanduser(feed_path),"r").read()

conf = json.loads(open("/etc/openstack/atlas/terminator.json").read())
tfc = utils.TerminatorFeedClient(**conf)

r = json.loads(feed_json)
rows = utils.parse_feeds(r)
rows.sort(key=operator.itemgetter("event_time"))



dbc = utils.DataBaseClient(**conf)

dbc.connect()
dbc.close()
