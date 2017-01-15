#!/usr/bin/env python

from terminator.app.db import tables, crud
from terminator.app.constants import (FULL, ACTIVE, TERMINATED, SUSPEND,
                                      SUSPENDED, DELETED, GLOBAL)
import mymocks
import mock
import uuid
import unittest
import datetime
import string
import json
import os

from terminator.app import utils
from terminator.app import terminator_app

CONF_FILE = "/etc/openstack/atlas/test_terminator.json"
TEST_CONF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "test-config.json")

TEST_ACCOUNT = 354934

class TestUtils(unittest.TestCase):
    def setUp(self):
        self.conf = json.loads(conf_text)
        json_text_file = os.path.join(os.path.dirname(__file__), "test.json")
        with open(json_text_file) as fp:
            json_text = fp.read()
        self.feed = json.loads(json_text)

    def test_feed_parser(self):
        # We are testing the feed parser so we don't need to connect to
        # Terminator
        tc = utils.TerminatorFeedClient(conf=self.conf)
        # Pretend we made a feed call and below is the feed object we got
        parsed_obj = tc.parse_entries(self.feed)
        pass

    def test_feed_client_conf_loader(self):
        tc = utils.TerminatorFeedClient(conf=self.conf)
        expected_feed_url = \
            string.join(["https://atom.prod.dfw1.us.ci.rackspace.net",
                         "/customer_access_policy/events"], sep='')
        self.assertEqual(expected_feed_url, tc.feed_url)
        self.assertEqual(tc.url, "https://identity.api.rackspacecloud.com")
        self.assertEqual(tc.passwd, "PASSWDHERE")
        self.assertEqual(tc.user, "USERHERE")

    def test_get_tenant_id(self):
        self.assertEqual(1023061,
                         utils.get_tenant_id(self.feed['feed']['entry'][0]))
        self.assertEqual(1022596,
                         utils.get_tenant_id(self.feed['feed']['entry'][1]))

    def test_get_event(self):
        self.assertEqual(SUSPENDED,
                         utils.get_event(self.feed['feed']['entry'][0]))
        self.assertEqual(TERMINATED,
                         utils.get_event(self.feed['feed']['entry'][1]))

    def test_get_event_datetime(self):
        self.assertEqual(
            datetime.datetime(2016, 11, 17, 2, 42, 8, 699000),
            utils.get_event_datetime(self.feed['feed']['entry'][0]))
        self.assertEqual(
            datetime.datetime(2016, 11, 17, 2, 0, 11, 162000),
            utils.get_event_datetime(self.feed['feed']['entry'][1]))

    def test_load_terminator_app_conf(self):
        clb = utils.LbaasClient(self.conf)
        self.assertEqual(clb.conf['clb']['passwd'], "somepasswd")
        self.assertEqual(clb.conf['clb']['user'], "someracker")
        self.assertEqual(clb.conf['clb']['dc'],
            {"somedc": { "endpoint": "someendpoint"},
             "anotherdc": {"endpoint": "anotherendpoint"}})

    @unittest.skip("not really wanting to test in production")
    def test_clb_client(self):
        clb = utils.LbaasClient()
        clb.set_dc('iad')
        lbs = clb.get_lbs(354934)
        self.assertTrue(type(lbs) is list)

    @unittest.skip("testing against the real terminator feed is slow.")
    def test_get_all_feeds(self):
        # It should be safe to test with the real terminator client
        tfc = utils.TerminatorFeedClient()
        tfc.get_token()
        entries = tfc.get_all_entries(25)
        self.assertTrue(len(entries) > 0)

    @unittest.skip("You need a real database to run this test.")
    def test_logger(self):
        l = terminator_app.TerminatorLogger()
        sess = crud.get_session()
        crud.get_curr_run(sess)
        l.set_tenant_id(354934)
        l.log("Testing if the logger works")
        l.log("Testing some more")
        l.log("hope the db didn't explode")

    @unittest.skip("Still trying to figure out how to automate this")
    def test_suspend_my_account(self):
        ta = terminator_app.TerminatorApp()
        self.assertTrue(ta.suspend_aid("TEST", 354934))
        nop()

    @unittest.skip("this one too")
    def test_scan_clb_dbs(self):
        ta = terminator_app.TerminatorApp()
        lbs = ta.get_all_lbs(354934)
        nop()

    @unittest.skip("this one too")
    def test_unsuspend_my_account(self):
        ta = terminator_app.TerminatorApp()
        self.assertTrue(ta.unsuspend_aid(354934))
        nop()

    @unittest.skip("Be carfull with this one")
    def test_delete_my_account(self):
        ta = terminator_app.TerminatorApp()
        self.assertTrue(ta.delete_aid(354934))
        nop()

    @mock.patch('terminator.app.utils.requests', autospec=True)
    def test_run_iteration(self, req):
        posts = []
        gets = []
        dels = []
        posts.append(mymocks.MockResponse({'access': {'token':
                                                          {'expires': 'Never',
                                                           'id': 'Id'}}},200))

        gets.append(mymocks.MockResponse(make_fake_feed([SUSPEND, FULL,
                                                 SUSPEND,TERMINATED]),
                                  200))
        gets.append(mymocks.MockResponse(make_fake_feed([]),200))

        #populate get_lbs for suspend
        populate_get_lbs(gets, ACTIVE)
        #expect the app to send four posts to delete the 4 lbs
        populate_responseobjects(posts, 202)

        #populate get_lbs for FULL access
        populate_get_lbs(gets, SUSPENDED)

        #expect the app to send four delete suspension calls
        populate_responseobjects(dels, 202)

        #time to suspend the LBs again.
        populate_get_lbs(gets, ACTIVE)

        #re suspending loadbalancers
        populate_responseobjects(posts,202)

        #finally delete the loadbalancers
        #populate gets for lbs during delete call
        populate_get_lbs(gets, SUSPENDED)

        #expect 4 delete calls to terminate the loadbalancers
        populate_responseobjects(dels, 202)


        req.post.side_effect = posts
        req.get.side_effect = gets
        req.delete.side_effect = dels
        test_conf = utils.load_config(utils.load_json(TEST_CONF_FILE))
        utils.create_tables(test_conf)
        ta = terminator_app.TerminatorApp(test_conf)
        ta.bump_run()
        ta.run_iteration()

        # Time to check the logs and action table to see if everything worked
        sess = crud.get_session(test_conf)

        expected_order_statuses = [(ACTIVE, SUSPENDED),
                                   (SUSPENDED, ACTIVE),
                                   (ACTIVE, SUSPENDED),
                                   (SUSPENDED, DELETED)]


        lb1234_ord = (sess.query(tables.Action)
                      .filter(tables.Action.lid==1234)
                      .filter(tables.Action.dc=='ord')
                      .order_by(tables.Action.time)
                      .all())

        self.assertActionsChangedFromTo(lb1234_ord, expected_order_statuses)
        lb4567_ord = (sess.query(tables.Action)
                      .filter(tables.Action.lid==4567)
                      .filter(tables.Action.dc=='ord')
                      .order_by(tables.Action.time)
                      .all())

        self.assertActionsChangedFromTo(lb1234_ord, expected_order_statuses)
        lb1234_dfw = (sess.query(tables.Action)
                      .filter(tables.Action.lid==1234)
                      .filter(tables.Action.dc=='dfw')
                      .order_by(tables.Action.time)
                      .all())

        self.assertActionsChangedFromTo(lb1234_ord, expected_order_statuses)
        lb4567_dfw = (sess.query(tables.Action)
                      .filter(tables.Action.lid==4567)
                      .filter(tables.Action.dc=='dfw')
                      .order_by(tables.Action.time)
                      .all())

        self.assertActionsChangedFromTo(lb1234_ord, expected_order_statuses)

        nop()


    def assertActionsChangedFromTo(self, action_list, expectedActions):
        for (i, ea) in enumerate(expectedActions):
            expected_from = ea[0]
            expected_to = ea[1]
            status_from = action_list[i].status_from
            status_to = action_list[i].status_to
            self.assertEquals(expected_from, status_from)
            self.assertEquals(expected_to, status_to)


def populate_responseobjects(gets, status):
    for i in xrange(0,4):
        gets.append(mymocks.MockResponse("blah", status))



def populate_get_lbs(gets,status):
    #populate requests for both datacenters
    #DFW
    gets.append(mymocks.MockResponse(make_fake_lbs([(1234,status),
                                                    (4567, status)]), 200))
    #ORD
    gets.append(mymocks.MockResponse(make_fake_lbs([(1234, status),
                                                    (4567, status)]), 200))


#lb_list should be of the form [(1234,ACTIVE),(5678,DELETED)]
def make_fake_lbs(lb_list):
    lbs_resp = []
    resp = {"accountLoadBalancers":lbs_resp}
    for (lid, status) in lb_list:
        lbs_resp.append({"loadBalancerId": lid, "status": status})
    return resp


def make_fake_feed(statuses):
    entries = []
    feed = {"feed":{"entry":entries}}
    dt = datetime.datetime(2016,1,1)
    for status in statuses:
        event = {"eventTime": dt.isoformat(), "dataCenter": GLOBAL,
                 "region": GLOBAL, "tenantId": TEST_ACCOUNT,
                 "product": {"status": status}}
        entry={"id": "urn:uuid:%s"%(str(uuid.uuid4())),
               "category": [{"term": "tid:%d"%(TEST_ACCOUNT,)}],
               "content": {"event": event}}
        dt = dt + datetime.timedelta(hours=1)
        entries.append(entry)
    return feed


conf_text = """
{
  "feed": {
    "url": "https://atom.prod.dfw1.us.ci.rackspace.net/customer_access_policy/events"
  },
  "db": "sqlite://",
  "clb": {
    "passwd": "somepasswd",
    "user": "someracker",
    "delay": 5,
    "dc": {
      "somedc": {
        "endpoint": "someendpoint"
      },
      "anotherdc": {
        "endpoint": "anotherendpoint"
      }
    }
  },
  "auth": {
    "passwd": "PASSWDHERE",
    "url": "https://identity.api.rackspacecloud.com",
    "user": "USERHERE"
  }
}

"""


def nop():
    pass

if __name__ == "__main__":
    unittest.main()
