from terminator.app import utils
from terminator.app.db import crud
from terminator.app.db import tables
import logging
import time

TERMINATOR_CHOMP_SIZE = 1000  # Chomp chomp


class TerminatorApp(object):
    def __init__(self, conf=None):
        self.conf = utils.load_config(conf)
        self.endpoints = {}
        self.sess = crud.get_session()
        self.lc = utils.LbaasClient(self.conf)
        self.tfc = utils.TerminatorFeedClient(self.conf)
        self.logger = TerminatorLogger(self.conf)
        self.delay = float(self.conf['clb']['delay'])
        for (dcname, dc_dict) in self.conf['clb']['dc'].iteritems():
            self.endpoints[dcname] = dc_dict['endpoint']


    def rest_session(self):
        self.sess = crud.get_session()

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

    def unsuspend_aid(self, terminator_id, aid):
        sess = crud.get_session(self.conf)
        lbs = self.get_all_lbs(aid)
        user = self.conf['clb']['user']
        self.logger.set_tenant_id(aid)
        self.logger.log("Unsuspending all LBS for account %d", aid)
        all_unsuspends_worked = True  # During borked loop set this to false
        for (dc, lb_list) in lbs['lbs'].iteritems():
            for lb in lb_list:
                lid = lb['lid']
                status = lb['status']
                if status != "SUSPENDED":
                    self.logger.log("Not unsuspending lb %d status %d",
                                    lid, status)
                    continue
                act = tables.Action(dc=dc, aid=aid, lid=lid,
                                    status_from=status, status_to="ACTIVE")
                sess.add(act)
                sess.commit()
                self.lc.set_dc(dc)
                req = self.lc.unsuspend_lb(terminator_id, lid)
                time.sleep(self.delay)
                if req.status_code != 200:
                    fmt = "Error got http %d when trying to suspend lb %d: %s"
                    self.logger.log(fmt, req.status_code, lid, req.text)
                    act.success = False
                    all_unsuspends_worked = False
                else:
                    act.success = True
                sess.merge(act)
                sess.commit()
        return all_unsuspends_worked

    def suspend_aid(self, terminator_id, aid):
        sess = crud.get_session(self.conf)
        lbs = self.get_all_lbs(aid)
        user = self.conf['clb']['user']
        self.logger.set_tenant_id(aid)
        self.logger.log("Suspending all LBS for account %d", aid)
        all_suspends_worked = True  # During borked loop set this to false
        for (dc, lb_list) in lbs['lbs'].iteritems():
            for lb in lb_list:
                self.lc.set_dc(dc)
                lid = lb['lid']
                status = lb['status']
                if status == "ERROR":
                    self.logger.log("Not suspending an error loadbalancer %d",
                                    lid)
                    continue
                if status == "SUSPENDED":
                    self.logger.log("Loadbalancer already suspended %d",
                                    lid)
                    continue
                if status != "ACTIVE":
                    self.logger.log("not suspending  loadbalancer %d from %s ",
                                    lid, status)
                    continue
                self.logger.log("Suspending lb %d", lid)
                act = tables.Action(dc=dc, aid=aid, lid=lid,
                                    status_from=status, status_to="SUSPENDED")
                sess.add(act)
                sess.commit()
                req = self.lc.suspend_lb(terminator_id, lid)
                time.sleep(self.delay)  #  Cause the api is fragile.
                if req.status_code != 202:
                    fmt = "Error got http %d when trying to suspend lb %d: %s"
                    self.logger.log(fmt, req.status_code, lid, req.text)
                    act.success = False
                    all_suspends_worked = False
                else:
                    act.success = True
                sess.merge(act)
                sess.commit()
        return all_suspends_worked

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
        msg = msg.replace("\n", " ")  # Line feeds are horrible in the db
        logobj = tables.Log(msg=msg,tenant_id=self.tenant_id)
        self.sess.add(logobj)
        self.sess.commit()
        try:
            l = getattr(logging, log_type)
            l(msg)
        except Exception, ex:
            logging.exception("Error writing to log database %s" % (msg,))