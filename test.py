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
from terminator.app import terminator_app

ta = terminator_app.TerminatorApp()


feed_path = "./terminator/test/test.json"
feed_json = open(os.path.expanduser(feed_path),"r").read()

conf = json.loads(open("/etc/openstack/atlas/terminator.json").read())

clb = utils.LbaasClient()
clb.set_dc('iad')
clb.get_lbs(354934)


tfc = utils.TerminatorFeedClient()
tfc.get_token()

feed_entries = tfc.get_all_entries(1000)

sess = crud.get_session()
crud.inc_curr_run(sess)
new_entries = crud.get_new_entries(sess,feed_entries)
crud.save_entries(sess, new_entries)


rows = sess.query(tables.Entry).all()



