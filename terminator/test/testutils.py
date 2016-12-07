#!/usr/bin/env python

import unittest
import datetime
from dateutil import tz
import string
import json
import os

from terminator.app import utils

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
        tc = utils.TerminatorFeedClient(**self.conf)
        # Pretend we made a feed call and below is the feed object we got
        parsed_obj = utils.parse_feeds(self.feed)
        pass

    def test_feed_client_conf_loader(self):
        tc = utils.TerminatorFeedClient(**self.conf)
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




conf_text = """
{
    "feed": {
        "url": "https://atom.prod.dfw1.us.ci.rackspace.net/customer_access_policy/events"
    },
    "auth": {
        "passwd": "PASSWDHERE",
        "url": "https://identity.api.rackspacecloud.com",
        "user": "USERHERE"
    },
    "db": "mysql://blahfuckingblackingblah"
}
"""

if __name__ == "__main__":
    unittest.main()
