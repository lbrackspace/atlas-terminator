from terminator.app import utils
from terminator.app.db import crud
from terminator.app.db import tables
import logging
import time
import sys

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
        self.run_id = None
        for (dcname, dc_dict) in self.conf['clb']['dc'].iteritems():
            self.endpoints[dcname] = dc_dict['endpoint']
        if tables.curr_run_id is None:
            self.bump_run()

    def run_iteration(self):
        try:
            sess = crud.get_session()
            self.bump_run_id(sess)
            self.run_terminator_client(sess)
            self.run_needs_push(sess)
            return True
        except:
            self.logger.set_tenant_id(0)
            self.logger.log("Error During run %d exception caught",
                            tables.curr_run_id, comment=utils.excuse(),
                            type="error")
            return False


    def bump_run_id(self, sess):
        self.run_id = crud.inc_curr_run(sess)
        self.logger.set_tenant_id(0)
        self.logger.log("starting run %d", self.run_id)

    def run_terminator_client(self, sess):
        self.logger.log("fetching new entries from terminator feed")
        r = self.get_new_terminator_entries()
        self.logger.log("found %d entries of which %d are new",
                        r['n_entries'], r['n_new_entries'])

    def run_needs_push(self, sess):
        ready_entries = crud.get_needs_push(sess)
        for entry in ready_entries:
            entry.num_attempts += 1
            sess.merge(entry)
            sess.commit()
            eid = entry.entry_id
            i = entry.id
            dc = entry.dc
            aid = entry.tenant_id
            region = entry.region
            self.logger.set_tenant_id(aid)
            if dc != "GLOBAL" or region != "GLOBAL":
                fmt = "skipping odd ball entry id %d %s with (region, dc)=%s",
                regdc = "(%s, %s)" % (region, dc)
                msg = fmt % (i, eid, regdc)
                self.logger.log(msg, type="warn")
                entry.needs_push = False
                entry.succeeded = False
                sess.merge(entry)
                sess.commit()
                continue
            self.logger.log("Event %s recieved for aid %s",
                            entry.event, aid)
            if entry.event == "SUSPEND":
                if self.suspend_aid(eid, aid):
                    entry_succeeded(sess, entry)
            elif entry.event == "FULL":
                if self.unsuspend_aid(aid):
                    entry_succeeded(sess, entry)
            elif entry.event == "TERMINATED":
                if self.delete_aid(aid):
                    entry_succeeded(sess, entry)


    def main_loop(self):
        while True:
            self.run_iteration(self)
            utils.wait_mod_minute(5)

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

    def unsuspend_aid(self, aid):
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
                    self.logger.log("Not unsuspending lb %d status %s",
                                    lid, status)
                    continue
                act = tables.Action(dc=dc, aid=aid, lid=lid,
                                    status_from=status, status_to="ACTIVE")
                sess.add(act)
                sess.commit()
                self.logger.log("Attempting to unsuspend %d_%d %s",
                                aid, lid, dc)
                self.lc.set_dc(dc)
                req = self.lc.unsuspend_lb(lid)
                time.sleep(self.delay)
                if req.status_code != 202:
                    fmt = "Error got http %d when trying to suspend lb %d: %s"
                    self.logger.log(fmt, req.status_code, lid, req.text)
                    act.success = False
                    all_unsuspends_worked = False
                else:
                    act.success = True
                sess.merge(act)
                sess.commit()
        sess.close()
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
                act = tables.Action(dc=dc, aid=aid, lid=lid,
                                    status_from=status, status_to="SUSPENDED")
                sess.add(act)
                sess.commit()
                self.logger.log("Attempting to suspend %d_%d %s",
                                aid, lid, dc)
                req = self.lc.suspend_lb(terminator_id.replace('-',''), lid)
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
        sess.close()
        return all_suspends_worked

    def delete_aid(self, aid):
        sess = crud.get_session(self.conf)
        lbs = self.get_all_lbs(aid)
        self.logger.set_tenant_id(aid)
        self.logger.log("Deleting all LBS for account %d", aid)
        all_deletes_success = True  # Flip this on failure
        for (dc, lb_list) in lbs['lbs'].iteritems():
            for lb in lb_list:
                lid = lb['lid']
                status = lb['status']
                if status != "ACTIVE" and status != "SUSPENDED":
                    fmt = "Not deleting lb %d_%d in %s its status is %s"
                    msg = fmt % (aid, lid, dc, status)
                    self.logger.log(msg, tenant_id=aid)
                    continue
                self.logger.log("attempting delete of %d_%d in %s",
                                aid, lid, dc)
                self.lc.set_dc(dc)
                act = tables.Action(dc=dc, aid=aid, lid=lid,
                                    status_from=status, status_to="DELETED")
                sess.add(act)
                sess.commit()
                if status == "ACTIVE":
                    req = self.lc.delete_lb(aid, lid)
                elif status == "SUSPENDED":
                    req = self.lc.delete_suspended_lb(lid)
                    # These are special
                else:
                    # The if statement above should have been a fail early
                    # test so this state should be impossible to reach
                    self.logging.log("Impossible state ERROR", type="error")
                    continue  # Continue anyways.
                time.sleep(self.delay)
                if req.status_code != 202:
                    fmt = "Error deleting lb %d_%d from %s http %d %s"
                    msg = fmt % (aid, lid, dc, req.status_code, req.text)
                    self.logger.log(msg, type="error")
                    all_deletes_success = False
                    act.success = False
                else:
                    act.success = True
                sess.merge(act)
                sess.commit()
        return all_deletes_success

    def get_all_lbs(self, aid):
        lbs = {}
        status_dict = {}
        lb_count = 0
        for (dc, endpoint) in self.endpoints.iteritems():
            self.lc.set_dc(dc)
            dc_lbs = self.lc.get_lbs(aid)
            lbs[dc] = []
            for lb in dc_lbs:
                status = lb['status']
                if status == "DELETED":
                    continue
                if status not in status_dict:
                    status_dict[status] = 0
                status_dict[status] += 1
                lbs[dc].append(lb)
                lb_count += 1
        return {'lbs': lbs, 'lb_count': lb_count, 'status': status_dict}

    # Create loadbalancers in each region for testing only
    def create_lbs(self, aid):
        self.logger.set_tenant_id(aid)
        for (dc, endpoint) in self.endpoints.iteritems():
            self.lc.set_dc(dc)
            self.logger.log("Creating loadbalancer in %s for %d",
                            dc, aid, )
            req = self.lc.create_lb(aid)
            if req.status_code != 202:
                self.logger.log("Failed to create lb for %s %d %s",
                                dc, aid, req.text)
            else:
                self.logger.log("Success adding lb in %s %d",
                                dc, aid)


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
        logobj = tables.Log(msg=msg, tenant_id=self.tenant_id)
        self.sess.add(logobj)
        self.sess.commit()
        try:
            l = getattr(logging, log_type)
            l(msg)
            sys.stdout.write(msg)
            sys.stdout.flush()
        except Exception, ex:
            logging.exception("Error writing to log database %s" % (msg,))


def entry_succeeded(sess, entry):
    entry.needs_push = False
    entry.succeeded = True
    entry.finished_time = tables.now()
    sess.merge(entry)
    sess.commit()


if __name__ == "__main__":
    ta = TerminatorApp()
    ta.main_loop()