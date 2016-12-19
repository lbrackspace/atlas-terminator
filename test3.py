#!/usr/bin/env python

from terminator.app.db import crud, tables
from terminator.app import utils
from terminator.app import terminator_app
import uuid
import json

SUCKERS_ACCOUNT = 354934

def create_events(events):
    sess = crud.get_session()
    for event in events:
        e = tables.Entry()
        e.dc = "GLOBAL"
        e.region = "GLOBAL"
        e.entry_id = str(uuid.uuid4())
        e.tenant_id = SUCKERS_ACCOUNT
        e.event_time = tables.now()
        e.event = event
        e.event_body = json.dumps({"pfft": "some_event"})
        e.needs_push = True
        e.created_time = tables.now()
        sess.add(e)
    sess.commit()


ta = terminator_app.TerminatorApp()

# Clean up old LBS for some suckers test account
#ta.delete_aid(SUCKERS_ACCOUNT)

# And create one per region
#ta.create_lbs(SUCKERS_ACCOUNT)

# Find any new Terminator feeds and store them in the database

#ta.get_new_terminator_entries()


# Mark the entries as if the're already done so they'll be ignored
# so that the main iteration loop ignores them during its pass

sess = crud.get_session()
entry_list = sess.query(tables.Entry).all()
#for entry in entry_list:
#    entry.succeeded = True
#    entry.needs_push = False
#    entry.finished = tables.now()
#    sess.merge(entry)
#sess.commit()

#Create bogus SUSUPEND FULL SUSPEND  TERMINATE events for the aid
create_events(["SUSPEND", "FULL","SUSPEND","TERMINATED"])
# now run the iteration and start debugging here
ta.run_iteration()
