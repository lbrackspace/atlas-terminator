
from terminator.app import terminator_app
from terminator.app import utils

ta = terminator_app.TerminatorApp()
lc = utils.LbaasClient()

ta.create_lbs(354934)
ta.get_new_terminator_entries()


ta.suspend_aid("some id here",354934)
