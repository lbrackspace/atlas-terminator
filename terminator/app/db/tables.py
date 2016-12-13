import datetime
import dateutil.tz
import sqlalchemy
from sqlalchemy import Integer, Boolean, Column, DateTime, String, Text, \
    Table, orm, ForeignKey, Index

metadata = sqlalchemy.MetaData()

curr_run_id = None

run_table = Table('run', metadata,
                  Column('id', Integer, primary_key=True, autoincrement=True),
                  Column('ran_at', DateTime, index=True),
                  mysql_engine='InnoDB',
                  mysql_charset='utf8')


class Run(object):
    def __init__(self, *args, **kw):
        self.ran_at = kw.get('ran_at', now())

    def to_dict(self):
        out = {}
        for attr in ['id', 'ran_at']:
            out[attr] = getattr(self, attr, None)
        return out

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return self.__str__()


entry_table = Table('entry', metadata,
                    Column('id', Integer, primary_key=True),
                    Column('run_id', Integer, index=True),
                    Column('dc', String(16)),
                    Column('region', String(16)),
                    Column('entry_id', String(45), unique=True),
                    Column('tenant_id', Integer, index=True),
                    Column('event_time', DateTime, index=True),
                    Column('event', String(16)),
                    Column('event_body', Text),
                    Column('needs_push', Boolean, index=True),
                    Column('num_attempts', Integer),
                    Column('created_time', DateTime),
                    Column('finished_time', DateTime),
                    Index('run_tenant_id', 'run_id', 'tenant_id'),
                    mysql_engine='InnoDB',
                    mysql_charset='utf8')


class Entry(object):
    def __init__(self, *args, **kw):
        global curr_run_id
        self.entry_id = kw.get('entry_id', None)
        self.run_id = kw.get('run_id', kw.get('run_id', curr_run_id)),
        self.dc = kw.get('dc', None)
        self.region = kw.get('region', None)
        self.tenant_id = kw.get('tenant_id', None),
        self.event_time = kw.get('event_time', None)
        self.event = kw.get('event', None)
        self.event_body = kw.get('entry_body', None)
        self.needs_push = kw.get('needs_push', None)
        self.num_attempts = kw.get('num_attempt', 0)
        self.created_time = kw.get('created_time', now())
        self.finished_time = kw.get('finished_time', None)

    def to_dict(self):
        out = {}
        for attr in ['id', 'dc', 'region', 'entry_id', 'run_id',
                     'tenant_id', 'event_time', 'event', 'event_body',
                     'needs_push', 'num_attempts', 'created_time',
                     'finished_time']:
            out[attr] = getattr(self, attr, None)
        return out

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return self.__str__()


action_table = Table('action', metadata,
                     Column('id', Integer, primary_key=True),
                     Column('run_id', Integer),
                     Column('dc', String(8)),
                     Column('aid', Integer),
                     Column('lid', Integer),
                     Column('status_from', String(32)),
                     Column('status_to', String(32)),
                     Column('time', DateTime, index=True),
                     Column('success', Boolean),
                     Column('comment', Text),
                     mysql_engine='InnoDB',
                     mysql_charset='utf8')


class Action(object):
    def __init__(self, *args, **kw):
        global curr_run_id
        self.aid = kw.get('aid')
        self.dc = kw.get('dc')
        self.lid = kw.get('lid')
        self.run = kw.get('run_id', kw.get('run_id', curr_run_id))
        self.status_from = kw.get('status_from')
        self.status_to = kw.get('status_to')
        self.time = kw.get('time', now())
        self.success = kw.get('success', False)

    def to_dict(self):
        out = {}
        for attr in ['id', 'run_id', 'dc', 'aid', 'lid', 'status_from',
                     'status_to', 'time', 'success']:
            out[attr] = getattr(self, attr, None)
        return out

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return self.__repr__()


log_table = Table('log', metadata,
                  Column('id', Integer, primary_key=True),
                  Column('run_id', Integer, index=True),
                  Column('msg', Text),
                  Column('tenant_id', Integer, index=True),
                  Column('created', DateTime, index=True),
                  mysql_engine='InnoDB',
                  mysql_charset='utf8')


class Log(object):
    def __init__(self, *args, **kw):
        global curr_run_id
        self.msg = kw.get('msg', None)
        self.run_id = kw.get('run_id', kw.get('run_id', curr_run_id))
        self.tenant_id = kw.get('tenant_id', None)
        self.created = kw.get('created', now())

    def to_dict(self):
        out = {}
        for attr in ['id', 'msg', 'run_id', 'tenant_id', 'created']:
            out[attr] = getattr(self, attr, None)
        return out

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return self.__str__()

orm.mapper(Entry, entry_table)
orm.mapper(Log, log_table)
orm.mapper(Run, run_table)
orm.mapper(Action, action_table)


def now():
    return datetime.datetime.now(dateutil.tz.tzutc()).replace(tzinfo=None)
