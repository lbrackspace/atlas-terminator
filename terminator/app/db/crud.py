import sqlalchemy
from terminator.app.db import tables
from sqlalchemy.orm import sessionmaker
from terminator.app import utils

DBSession = None


def get_session(conf=None):
    global DBSession
    if DBSession is None:
        engine = utils.get_db_engine(conf)
        DBSession = sessionmaker(bind=engine)
    return DBSession()


def inc_curr_run(sess):
    run = tables.Run()
    sess.add(run)
    sess.commit()
    run_id = run.id
    tables.curr_run_id = run_id
    return run_id


def get_curr_run(sess):
    col = tables.Run.id
    run = sess.query(tables.Run).order_by(sqlalchemy.desc(col)).first()
    run_id = run.id
    tables.curr_run_id = run_id
    return run_id


def get_needs_push(sess):
    q = sess.query(tables.Entry).filter(tables.Entry.needs_push==1)
    rows = q.order_by(tables.Entry.event_time).all()
    sess.commit()
    return rows


def get_entries_by_entry_ids(sess, entry_id_list):
    rows = sess.query(tables.Entry).filter(tables.Entry.entry_id.in_(
        entry_id_list)).all()
    sess.commit()
    return rows


def get_new_entries(sess, tf_entries):
    new_entries = []
    tf_ids = [tfe['entry_id'] for tfe in tf_entries]
    db_entries = get_entries_by_entry_ids(sess, tf_ids)
    db_ids = set([dbe.entry_id for dbe in db_entries])
    for tfe in tf_entries:
        if tfe['entry_id'] not in db_ids:
            db_entry = tables.Entry(**tfe)
            new_entries.append(db_entry)
    return new_entries


def save_entries(sess, entry_list):
    sess.bulk_save_objects(entry_list)
    sess.commit()