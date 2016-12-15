#!/usr/bin/env python

import sqlalchemy
from terminator.app.db import tables
import base64
import dateutil.parser
import dateutil.tz
import operator
import requests
import logging
import json
import os

DEFAULT_CONF_FILE = "/etc/openstack/atlas/terminator.json"
engine = None


class TerminatorFeedClient(object):
    def __init__(self, conf=None):
        conf = load_config(conf)
        self.url = conf['auth']['url']
        self.user = conf['auth']['user']
        self.passwd = conf['auth']['passwd']
        self.token = None
        self.expires = None
        self.feed_url = conf['feed']['url']
        self.conf = conf

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

    # Keep grabing feed entries untill you can find no more
    # limit = the amount of entries to grab at a time
    def get_all_entries(self, limit):
        entries = []
        kw = {'params': {'marker': 'last', 'limit': limit}}
        end_loop = False # It'd be nice if python had do while loops
        while True:
            if end_loop:
                break
            try:
                r = self.get_feeds(**kw)
                feed_obj = json.loads(r.text)
                n_entries = feed_obj['feed']['entry']
                logging.info('fetched %d etnries', n_entries)
                kw['params']['marker'] = feed_obj['feed']['entry'][0]['id']
                entries.extend(self.parse_entries(feed_obj))
            except:
                logging.info("Exiting entry loop for total of %d entries",
                             len(entries))
                end_loop = True
            entries.sort(key=operator.itemgetter('event_time'))
        return entries

    def parse_entries(self,feed_obj):
        feed = feed_obj['feed']
        entries = []
        for entry in feed['entry']:
            eid = entry['id']
            tid = get_tenant_id(entry)
            dt = get_event_datetime(entry)
            ev = get_event(entry)
            (dc, region) = get_region_dc(entry)
            entries.append({'entry_id': eid, 'tenant_id': tid,
                            'event_time': dt, 'event': ev, 'dc': dc,
                            'region': region,
                            'entry_body': json.dumps(entry)})
        return entries


class LbaasClient(object):
    def __init__(self, conf=None):
        self.conf = load_config(conf)
        self.dc = None
        user = self.conf['clb']['user']
        passwd = self.conf['clb']['passwd']
        realm = base64.standard_b64encode("%s:%s" % (user, passwd))
        self.headers = {'accept': 'application/json',
                        'content-type': 'application/json',
                        'Authorization': 'BASIC %s' % (realm,)}

    def set_dc(self, dc):
        self.dc = dc

    def suspend_lb(self, ticket_id, lid):
        susp = {"reason": "Cause I said so",
                "ticket": {
                    "comment": "Terminator feed request",
                    "ticketId": ticket_id},
                "user": self.conf['clb']['user']}
        uri = "management/loadbalancers/%d/suspension" % (lid,)
        dc = self.dc
        ep = self.conf['clb']['dc'][dc]['endpoint']
        data = json.dumps(susp, indent=4)
        url = ep + uri
        req = requests.post(url, data=data, headers=self.headers)
        return req

    def unsuspend_lb(self, terminator_feed_id, lid):
        uri = "management/loadbalancers/%d/suspension" % (lid,)
        dc = self.dc
        ep = self.conf['clb']['dc'][dc]['endpoint']
        url = ep + uri
        req = requests.delete(url, headers=self.headers)
        return req

    # For testing cause my account keeps getting cleaned out
    def create_lb(self, aid):
        nodes = [{"address": "216.58.216.196", "port": 80,
                 "condition": "ENABLED"}]
        vips = [{"type": "PUBLIC"}]
        lb = {"name": "terminator_lb_test", "port": 80, "protocol": "HTTP",
              "virtualIps": vips, "nodes": nodes}
        uri = "%d/loadbalancers" % (aid, )
        dc = self.dc
        ep = self.conf['clb']['dc'][dc]['endpoint']
        obj = {"loadBalancer": lb}
        data = json.dumps(obj, indent=4)
        url = ep + uri
        req = requests.post(url, headers=self.headers, data=data)
        text = req.text
        return req

    def get_lbs(self, aid):
        out = []
        dc = self.dc
        ep = self.conf['clb']['dc'][dc]['endpoint']
        uri = "management/accounts/%d/loadbalancers" % (aid, )
        url = ep + uri
        req = requests.get(url, headers=self.headers)
        if req.status_code == 404:
            logging.info("coulden't find account %d in region %s skipping",
                         aid, dc)
            return []  # No loadbalancers found most likely not our account

        if req.status_code != 200:
            logging.warn("couldn't get lbs for account %d %d %s",
                         aid, req.status_code, req.text)
            return []
        lbs = json.loads(req.text)
        for lb in lbs['accountLoadBalancers']:
            status = lb['status']
            lid = lb['loadBalancerId']
            out.append({'status': status, 'lid': lid})
        return out


def load_config(conf=None):
    if conf is None:
        conf = load_json(DEFAULT_CONF_FILE)
    return conf

def get_tenant_id(entry):
    tid = None
    try:
        tid = int(entry['content']['event']['tenantId'])
    except (ValueError, KeyError) as ex:
        pass
    return tid


def get_region_dc(entry):
    (dc, region) = (None, None)
    try:
        dc = entry['content']['event']['dataCenter']
    except KeyError:
        pass
    try:
        region = entry['content']['event']['region']
    except KeyError:
        pass
    return (dc, region)

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
    with open(full_path, "r") as fp:
        json_text = fp.read()
        obj = json.loads(json_text)
    return obj


def save_json(file_path, obj):
    full_path = os.path.expanduser(file_path)
    with open(full_path, "w") as fp:
        json_text = json.dumps(obj, indent=4)
        fp.write(json_text)


def get_db_engine(conf=None,echo=False):
    global engine
    if conf is None:
        conf = load_json(DEFAULT_CONF_FILE)
    if engine is None:
        engine = sqlalchemy.create_engine(conf['db'], echo=echo)
    return engine


# Only run once during the life time of the app
def create_tables(conf=None):
    engine = get_db_engine(conf=conf)
    tables.metadata.create_all(engine)

