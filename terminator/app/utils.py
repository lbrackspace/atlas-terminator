#!/usr/bin/env python

import MySQLdb.cursors
import MySQLdb
import dateutil.parser
import dateutil.tz
import datetime
import operator
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

log_fmt = """
insert into log(tenant_id, created_time, log)
values(%(tenant_id)s,%(created_time)s,%(log)s)"""

entry_fmt = """
insert into entry(entry_id,tenant_id,event_time,event,entrybody,
                  is_our_account,needs_push,created_timestamp,
                  finished_timestamp,num_attempts)
        values(%(entry_id)s,%(tenant_id),%(event_time),%(event),%(entrybody),
               %(is_our_account),%(needs_push),%(created_timestamp),
               %(finished_timestamp)s,%(num_attempts)s)
"""


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

    def log(self, *args):
        log_entry = self._log(*args)
        self._savelog([log_entry])

    def _savelog(self, rows):
        self.cur.executemany(log_fmt, rows)
        self.con.commit()

    def select_entries_by_uuid(self, uuids):
        query = self._select_uuids_query_builder(uuids)
        r = self.cur.execute(query)
        return r.fetchall()

    def new_entries(self, feed_entries, db_entries):
        dt = now()
        new_entries_list = []
        db_uuids = set([de['uuid'] for de in db_entries])
        for fe in feed_entries:
            if fe['entry_id'] in db_uuids:
                continue #We already have this one skipping
            ne = {'entry_id': fe['entry_id'],
                  'tenant_id': fe['tenant_id'],
                  'event_time': fe['event_time'],
                  'event': fe['event'],
                  'entry_body': fe['entry_body'],
                  'is_our_account': None,
                  'needs_push': None,
                  'created_time': dt,
                  'finished_time': None,
                  'num_attempts': 0}
            new_entries_list.append(ne)
        return new_entries_list

    def save_new_entries(self, feed_entries, db_entries):
        new_entries_list = self.new_entries(feed_entries, db_entries)
        self.cur.executemany(entry_fmt, new_entries_list )
        self.con.commit()

    def _select_entries_by_uuid_builder(self, uuid_list):
        query = ["select * from entry where uuid in ("]
        col_fmts = []
        for uuid in uuid_list:
            fmt = "\"%s\"" % MySQLdb.escape_string(uuid)
            col_fmts.append(fmt)
        query.append(','.join(col_fmts))
        query.append(")")
        return ''.join(query)

    def _log(self, *args):
        cargs = list(args[:])
        (con, cur) = (self.con, self.cur)
        tenant_id = None
        try:
            tenant_id = int(cargs[0])
            cargs.pop(0)
        except ValueError:
            pass  # First argument is the format string instead of tenant_id
        #log = MySQLdb.escape_string(cargs[0] % tuple(cargs[1:]))
        log = cargs[0] % tuple(cargs[1:])
        created_time = now()   #UTC time but stripped cause mysql can't
                               #handle timezones
        row = {"created_time": created_time, "tenant_id": tenant_id,
               "log": log}
        return row


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


def now():
    return datetime.datetime.now(dateutil.tz.tzutc()).replace(tzinfo=None)

