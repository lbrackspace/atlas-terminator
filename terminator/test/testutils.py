#!/usr/bin/env python

from terminator.app.db import tables, crud
import unittest
import datetime
import string
import json
import os

from terminator.app import utils
from terminator.app import terminator_app

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
        self.assertEqual("SUSPENDED",
                         utils.get_event(self.feed['feed']['entry'][0]))
        self.assertEqual("TERMINATED",
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

    @unittest.skip("Yea this one looks real")
    def test_run_iteration(self):
        ta = terminator_app.TerminatorApp()
        self.assertTrue(ta.run_iteration())

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
