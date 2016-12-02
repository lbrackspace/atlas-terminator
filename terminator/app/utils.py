#!/usr/bin/env python

import MySQLdb.cursors
import MySQLdb
import dateutil.parser
import logging
import requests
import json

# The configuration **kw argument for the below classes can be loaded from json and passed in via the
# the keywords parameter of the classes for exampple
# for example the see the json blob below
# {
#  "feed": {
#     "url": "https://atom.prod.dfw1.us.ci.rackspace.net/customer_access_policy/e$
#   },
#   "db": {
#     "passwd": "DB_PASSWD",
#     "host": "DB_HOST_OR_IP",
#     "db": "loadbalancing",
#     "user": "lbaas"
#   },
#   "auth": {
#     "passwd": "IDENTITY_PASSWD",
#     "url": "https://identity.api.rackspacecloud.com",
#     "user": "IDENTITY USER"
#   }
# }
#
# The following can be passed in such as
#
# conf = json.loads(above_example)
# tfc = TerminatorFeedClient(**conf)
# dbc = DataBaseClient(**conf)


class TerminatorFeedClient(object):
    def __init__(self, *args, **kw):
        self.url = kw['auth']['url']
        self.user = kw['auth']['user']
        self.passwd = kw['auth']['passwd']
        self.token = None
        self.expires = None
        self.feed_url = kw['feed']['url']

    def get_token(self):
        up = {'username': self.user, 'password': self.passwd}
        payload = {'auth': {'passwordCredentials': up}}
        hdr = {'accept':'application/json', 
               'content-type': 'application/json'}
        uri = self.url + "/v2.0/tokens"
        r = requests.post(uri, headers=hdr, data=json.dumps(payload))
        obj = json.loads(r.text)
        token = obj["access"]["token"]["id"]
        expires = obj["access"]["token"]["expires"]
        self.token = token
        self.expires = expires
        return {'token': token, 'expires': expires}

    # Use kw = {'params': {'marker': 'last','limit': 1000}}
    # To get the most feeds started from the oldest to newest
    def get_feeds(self, *arg, **kw):
        hdrs = {'x-auth-token': self.token,
                'accept': 'application/vnd.rackspace.atom+json'}
        url = self.feed_url
        req_kw = {'headers': hdrs}
        if "params" in kw:
            req_kw['params'] = kw['params']

        req = requests.get(self.feed_url, **req_kw)
        return req


class DataBaseClient(object):
    def __init__(self, *args, **kw):
        self.mysql_creds = kw["db"]
        self.con = None
        self.cur = None

    def connect(self):
        self.con = MySQLdb.connect(**self.mysql_creds)
        self.cur = self.con.cursor(MySQLdb.cursors.DictCursor)

    def close(self):
        self.cur.close()
        self.con.close()
        (self.con, self.cur) = (None, None)


def get_tenant_id(entry):
    tid = None
    try:
        tid = int(entry['content']['event']['tenantId'])
    except (ValueError, KeyError) as ex:
        pass
    return tid


def parse_feeds(feed_obj):
    feed = feed_obj['feed']
    entries = []
    for entry in feed['entry']:
        eid = entry['id']
        tid = get_tenant_id(entry)
        dt = get_event_datetime(entry)
        ev = get_event(entry)
        entries.append({'entry_id': eid, 'tenant_id': tid,
                        'event_time': dt, 'event': ev,
                        'entry_body': entry})
    return entries


def get_event(entry):
    event = None
    try:
        event = entry['content']['event']['product']['status']
    except KeyError:
        pass
    return event

def get_event_datetime(entry):
    dt = None
    try:
        iso8601_date = entry['content']['event']['eventTime']
        dt = dateutil.parser.parse(iso8601_date)
    except (ValueError, KeyError) as ex:
        pass
    return dt
