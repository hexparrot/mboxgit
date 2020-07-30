#!/usr/bin/env python3

"""
A python script to convert mbox mailboxes into git repositories.
All body content and attachments are mapped to random names,
stored preferably with encryption, and can be recalled via
email attachment or direct connect.

Primary usecase is for systems with limited connectivity
and avoiding sneakernet
"""

__author__ = "William Dizon"
__license__ = "GNU GPL v3.0"
__version__ = "0.0.1"
__email__ = "wdchromium@gmail.com"

class mbox_to_git(object):
    def __init__(self, mbox_path):
        import mailbox

        self.mbox_fp = mbox_path
        self.mailbox = None
        try:
            self.mailbox = mailbox.mbox(mbox_path)
        except IsADirectoryError:
            raise RuntimeError("provided path is not an mbox file")
        except AttributeError:
            raise RuntimeError("provided path is not an mbox file")
        else:
            self.mailbox.lock()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.mailbox.unlock()
        self.mailbox.close()
