#!/usr/bin/env python

from terminator.app import utils
from terminator.app import terminator_app
import sys

if __name__ == "__main__":
    conf = utils.load_config(conf=None)
    if "--dryrun" in sys.argv:
        conf['dryrun'] = True
    ta = terminator_app.TerminatorApp(conf=conf)
    if conf.get('dryrun', False):
        ta.run_iteration()  # This is a dry run so do one iteration
    else:
        ta.main_loop()