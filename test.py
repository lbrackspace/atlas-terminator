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
tfc.get_token()
kw = {'params': {'marker': 'last','limit': 1000}}

#r = tfc.get_feeds(**kw)
#feeds = json.loads(r.text)
#feed_entries = utils.parse_feeds(feeds)


r = json.loads(feed_json)
feed_entries = utils.parse_feeds(r)
entry_ids = [e["entry_id"] for e in feed_entries]


dbc = utils.DataBaseClient(**conf)
dbc.connect()

#check if these entries are in the databases
db_entries = dbc.select_entries_by_entry_ids(entry_ids)
new_entries = dbc.get_new_entries(feed_entries, db_entries)
dbc.save_new_entries(new_entries)
