#!/usr/bin/env python

import sqlalchemy
import operator
import dateutil
import json
import sys
import os

from terminator.app import utils
from terminator.app.db import crud
from terminator.app.db import tables

feed_path = "./terminator/test/test.json"
feed_json = open(os.path.expanduser(feed_path),"r").read()

conf = json.loads(open("/etc/openstack/atlas/terminator.json").read())
tfc = utils.TerminatorFeedClient(conf)
tfc.get_token()
kw = {'params': {'marker': 'last','limit': 1000}}

r = tfc.get_feeds(**kw)
feeds = json.loads(r.text)
feed_entries = utils.parse_feeds(feeds)

r = json.loads(feed_json)
feed_entries = utils.parse_feeds(r)

sess = crud.get_session()
crud.inc_curr_run(sess)
new_entries = crud.get_new_entries(sess,feed_entries)
crud.save_entries(sess, new_entries)


