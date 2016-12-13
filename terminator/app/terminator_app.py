from terminator.app import utils
from terminator.app.db import crud
from terminator.app.db import tables
import logging

TERMINATOR_CHOMP_SIZE = 1000  # Chomp chomp


class TerminatorApp(object):
    def __init__(self, conf=None):
        self.conf = utils.load_config(conf)
        self.endpoints = {}
        self.sess = None
        self.lc = utils.LbaasClient(self.conf)
        self.tfc = utils.TerminatorFeedClient(self.conf)
        for (dcname, dc_dict) in self.conf['clb']['dc'].iteritems():
            self.endpoints[dcname] = dc_dict['endpoint']

    def bump_run(self):
        sess = crud.get_session(self.conf)
        run_id = crud.inc_curr_run(sess)
        return run_id

    # Grab entries from terminator feed then stuff all the new ones
    # Into the database so we can call the handle method below
    def get_new_terminator_entries(self):
        self.tfc.get_token()
        feed_entries = self.tfc.get_all_entries(TERMINATOR_CHOMP_SIZE)
        n_entries = len(feed_entries)
        sess = crud.get_session()
        new_entries = crud.get_new_entries(sess, feed_entries)
        crud.save_entries(sess, new_entries)
        n_new_entries = len(new_entries)
        return {"n_entries": n_entries, "n_new_entries": n_new_entries}

    def suspend_aid(self, aid):
        sess = crud.get_session(self.conf)
        lbs = self.get_all_lbs(aid)
        user = self.conf['clb']['user']

        for (dc, dc_lbs) in lbs.iteritems():
            endpoint = self.endpoints[dc]
            




    def get_all_lbs(self, aid):
        lbs = {}
        lb_count = 0
        for (dc, endpoint) in self.endpoints.iteritems():
            self.lc.set_dc(dc)
            dc_lbs = self.lc.get_lbs(aid)
            lbs[dc] = []
            for lb in dc_lbs:
                if lb['status'] == "DELETED":
                    continue
                lbs[dc].append(lb)
                lb_count += 1
        return {'lbs': lbs, 'lb_count': lb_count}


# Log via python and to the database
class TerminatorLogger(object):
    def __init__(self, conf=None):
        self.tenant_id = 0
        self.conf = utils.load_config(conf)
        self.sess = None

    def set_tenant_id(self, tid):
        self.tenant_id = tid

    def reset_session(self):
        self.sess = crud.get_session()

    def log(self, fmt, *args, **kw):
        log_type = kw.pop('type', 'info')  # info, error, warn, debug
        if self.sess is None:
            self.reset_session()
        msg = fmt % args
        logobj = tables.Log(msg=msg, tenant_id=self.tenant_id)
        self.sess.add(logobj)
        self.sess.commit()
        l = getattr(logging, log_type)
        l(msg)