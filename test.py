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
r = tfc.get_feeds(**kw)
feeds = json.loads(r.text)
entries = utils.parse_feeds(feeds)
uuids = [e["entry_id"] for e in entries]
#r = json.loads(feed_json)
#entries = utils.parse_feeds(r)

dbc = utils.DataBaseClient(**conf)
dbc.connect()

dbc._select_entries_by_uuid_builder(uuids)

dbc.log("No tenant\";inject code here")
dbc.log(-1, "tenant_id")

