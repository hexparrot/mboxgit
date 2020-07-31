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
    def __init__(self, mbox_path, repodir="mboxrepo"):
        import mailbox

        self.mbox_fp = mbox_path
        self.repodir = repodir
        self.mailbox = None
        self.messages = []

        try:
            self.mailbox = mailbox.mbox(mbox_path)
        except IsADirectoryError:
            raise RuntimeError("provided path is not an mbox file")
        except AttributeError:
            raise RuntimeError("provided path is not an mbox file")
        else:
            self.mailbox.lock()
            self.messages = [msg for msg in self.mailbox]

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.mailbox.unlock()
        self.mailbox.close()

    def init_repo(self):
        import os
        try:
            os.mkdir(self.repodir)
        except FileExistsError:
            raise RuntimeError("repo path already exists--it shouldn't before init_repo!")

        import subprocess
        subprocess.call("git init",
                        stdout=subprocess.PIPE,
                        cwd=self.repodir,
                        shell=True)

        from getpass import getuser
        self.set_user(getuser(), "%s@local" % getuser())

    def set_user(self, user, email):
        import subprocess
        commands = """
        git config user.name "%s"
        git config user.email "%s"
        """ % (user, email)

        subprocess.call(commands,
                        stdout=subprocess.PIPE,
                        cwd=self.repodir,
                        shell=True)

    def process_email(self, email):
        def fill_file(data, encoding='ascii'):
            ascii_as_bytes = data.encode('ascii')
            if encoding == 'base64':
                import base64
                message_bytes = base64.b64decode(ascii_as_bytes)
            else:
                message_bytes = ascii_as_bytes

            import tempfile
            t_filedesc, t_filepath = tempfile.mkstemp(prefix='', dir=self.repodir)
            open_file = open(t_filepath, 'w+b')
            open_file.write(message_bytes)
            open_file.flush()
            open_file.close()

            return (t_filedesc, t_filepath, len(message_bytes))

        import os

        processed_parts = []
        split_parts = email.get_payload()

        if isinstance(split_parts, list): #this is a multipart email
            for p in split_parts:
                final_filename = p.get_filename('body') #fallback if multipart, but not an attachment
                encoding = p.get('Content-Transfer-Encoding')
                tmp_filedesc, tmp_filepath, tmp_size = fill_file(p.get_payload(), encoding)
                processed_parts.append( (tmp_filepath, final_filename, tmp_size) )
        else: #single part email means content provided directly as string
            final_filename = 'body'
            tmp_filedesc, tmp_filepath, tmp_size = fill_file(split_parts)
            processed_parts.append( (tmp_filepath, final_filename, tmp_size) )

        return processed_parts

    def create_summary(self, processed_parts):
        import os
        summary = []
        for fp, final_name, fsize in processed_parts:
            summary.append("%s:%s:%i" % (os.path.basename(fp), final_name, fsize))
        return summary
