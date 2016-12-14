
from terminator.app import terminator_app
from terminator.app import utils

ta = terminator_app.TerminatorApp()
lc = utils.LbaasClient()
lbs = ta.get_all_lbs(354934)
lc.set_dc('dfw')
ta.get_new_terminator_entries()


ta.suspend_aid("some id here",354934)
