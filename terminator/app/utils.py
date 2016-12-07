#!/usr/bin/env python

import sqlalchemy
from terminator.app.db import tables
import dateutil.parser
import dateutil.tz
import datetime
import operator
import logging
import requests
import json
import os

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

DEFAULT_CONF_FILE = "/etc/openstack/atlas/terminator.json"

class TerminatorFeedClient(object):
    def __init__(self, conf=None):
        if conf is None:
            conf = load_json(DEFAULT_CONF_FILE)
        self.url = conf['auth']['url']
        self.user = conf['auth']['user']
        self.passwd = conf['auth']['passwd']
        self.token = None
        self.expires = None
        self.feed_url = conf['feed']['url']

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
                        'entry_body': json.dumps(entry)})
    return sorted(entries, key=operator.itemgetter("event_time"))


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
        dt = dateutil.parser.parse(iso8601_date).astimezone(
            dateutil.tz.tzutc()).replace(tzinfo=None) #Timezones have to be
                                                      #Striped for MySQL
    except (ValueError, KeyError) as ex:
        pass
    return dt


def load_json(file_path):
    full_path = os.path.expanduser(file_path)
    with open(full_path) as fp:
        json_text = fp.read()
        obj = json.loads(json_text)
    return obj


def get_db_engine(conf=None):
    if conf is None:
        conf = load_json(DEFAULT_CONF_FILE)
    engine = sqlalchemy.create_engine(conf['db'], echo=True)
    return engine


# Only run once during the life time of the app
def create_tables(conf=None):
    engine = get_db_engine(conf=conf)
    tables.metadata.create_all(engine)

