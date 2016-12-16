
from terminator.app import terminator_app
from terminator.app import utils
from terminator.app.db import crud, tables

ta = terminator_app.TerminatorApp()
lc = utils.LbaasClient()

sess = crud.get_session()

qb = sess.query(tables.Entry).filter(needs_push=1)
qb = qb.order_by(tables.Entry.event_time).all()

ta.create_lbs(354934)

lbs = ta.get_all_lbs(354934)

ta.get_new_terminator_entries()


ta.suspend_aid("some id here",354934)

ta.unsuspend_aid(354934)

ta.delete_aid(354934)


for i in xrange(0, len(entries)):
    e = entries[i]
    uid = e.entry_id.split(":")[-1]
    e.entry_id = uid
    sess.merge(e)

