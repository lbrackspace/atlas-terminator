#!/usr/bin/env python

from terminator.app.db import crud, tables
from terminator.app import utils
from terminator.app import terminator_app
import uuid
import json


ta = terminator_app.TerminatorApp()

# Clean up old LBS for account 354934
ta.delete_aid(354934)

# And create one per region
ta.create_lbs(354934)

# Find any new Terminator feeds and store them in the database

ta.get_new_terminator_entries()

# Mark the entries as if the're already done so they'll be ignored
# so that the main iteration loop ignores them during its pass

sess = crud.get_session()
entry_list = sess.query(tables.Entry).all()
for entry in entry_list:
    entry.succeeded = True
    entry.needs_push = False
    entry.finished = tables.now()
    sess.merge(entry)
sess.commit()

#Create bogus SUSUPEND FULL SUSPEND  TERMINATE events for the aid

for event in ["SUSPEND", "FULL", "SUSPEND", "TERMINATE"]:
    e = tables.Entry()
    e.dc = "GLOBAL"
    e.region = "GLOBAL"
    e.entry_id = str(uuid.uuid4())
    e.tenant_id = 354934
    e.event_time = tables.now()
    e.event = event
    e.event_body = json.dumps({"pfft":"some_event"})
    e.needs_push = True
    e.created_time = tables.now()
    sess.add(e)
sess.commit()

# now run the iteration and start debugging here

ta.iteration_body()

