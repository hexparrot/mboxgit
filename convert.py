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

import os
import subprocess

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

    def check_clean_before(self, func):
        def wrapper(*args, **kwargs):
            if not self.clean: raise RuntimeError('working tree not clean prior to action; aborting')
            return func(*args, **kwargs)
        return wrapper

    def check_clean_after(self, func):
        def wrapper(*args, **kwargs):
            retval = func(*args, **kwargs)
            if not self.clean: raise RuntimeError('working tree not clean after action; aborting')
            return retval
        return wrapper

    def init_repo(self,
                  abort_if_exists=False,
                  encrypted=False):
        try:
            os.mkdir(self.repodir)
        except FileExistsError:
            if abort_if_exists:
                raise RuntimeError("repo path already exists--it shouldn't before init_repo!")

        subprocess.call("git init",
                        stdout=subprocess.PIPE,
                        cwd=self.repodir,
                        shell=True)

        if encrypted:
            commands = """
            git secret init;
            git add .;
            git commit -m "initializing git-secret module";
            """
            subprocess.call(commands,
                            stdout=subprocess.PIPE,
                            cwd=self.repodir,
                            shell=True)

        from getpass import getuser
        self.set_user(getuser(), "%s@local" % getuser())

    def tell_secret(self, email):
        commands = """
        git secret tell %s;
        git add .;
        git commit -m "adding %s gpg identity"
        """ % (email, email)

        subprocess.call(commands,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        cwd=self.repodir,
                        shell=True)

    def set_user(self, user, email):
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

        processed_parts = []
        split_parts = email.get_payload()
        subject = email.get('subject')

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

        return (subject, processed_parts)

    def create_summary(self, processed_parts):
        summary = []
        for fp, final_name, fsize in processed_parts:
            summary.append("%s:%s:%i" % (os.path.basename(fp), final_name, fsize))
        return summary

    def make_commit(self, subject, summary):
        commands = """
        git add .;
        git commit -m "%s" -m "%s";
        """ % (subject, '\n'.join(summary))

        subprocess.call(commands,
                        stdout=subprocess.PIPE,
                        cwd=self.repodir,
                        shell=True)
        return self.head_id

    def make_secret_commit(self, subject, summary):
        ignored_files = []
        added_files = ['git add .gitignore;', 'git add .gitsecret/paths/mapping.cfg;']
        encrypted_summary = []
        with open(os.path.join(self.repodir, '.gitignore'), 'a') as gi:
            for s in summary:
                orig_name = s.split(':')[0]
                ignored_files.append("git secret add %s;" % orig_name)
                added_files.append("git add %s.secret;" % orig_name)
                encrypted_summary.append(s.replace(':', '.secret:', 1))
                gi.write("%s\n" % orig_name)

        commands = """
        %s
        git secret hide -d;
        %s
        git commit -m "%s" -m "%s";
        """ % ('\n'.join(ignored_files),
               '\n'.join(added_files),
               subject,
               '\n'.join(encrypted_summary))

        subprocess.call(commands,
                        stdout=subprocess.PIPE,
                        cwd=self.repodir,
                        shell=True)
        return self.head_id

    @property
    def head_id(self):
        commands = "git rev-parse HEAD"

        try:
            output = subprocess.check_output(commands,
                                             cwd=self.repodir,
                                             stderr=subprocess.DEVNULL,
                                             shell=True)
        except subprocess.CalledProcessError:
            return None
            # Command 'git rev-parse --short HEAD' returned non-zero exit status 128.
            # thrown when no repository yet init'ed
        else:
            return output.strip().decode('ascii')

    @property
    def commit_count(self):
        commands = "git rev-list --count HEAD"

        try:
            output = subprocess.check_output(commands,
                                             cwd=self.repodir,
                                             stderr=subprocess.DEVNULL,
                                             shell=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return 0
        else:
            return int(output.strip().decode('ascii'))

    @property
    def clean(self):
        commands = "git status --porcelain"

        output = subprocess.check_output(commands,
                                         cwd=self.repodir,
                                         shell=True)
        return not bool(output.strip())

    def get_commit_of_file(self, fn):
        commands = "git rev-list -1 HEAD %s" % fn

        output = subprocess.check_output(commands,
                                         cwd=self.repodir,
                                         shell=True)
        return output.strip().decode('ascii')

    def get_commit_filelist(self, commit):
        commands = "git show --no-commit-id --name-only -r %s" % commit 

        output = subprocess.check_output(commands,
                                         cwd=self.repodir,
                                         shell=True)
        
        line_output = output.strip().decode('ascii').split('\n')
        retval = []
        for line in line_output:
            split = line.split(' ')
            if len(split[0])==6 and len(split[1])==40 and split[0]=='commit': break
            retval.append(line)
        return retval

if __name__ == '__main__':
    with mbox_to_git('pi') as instance:
        instance.init_repo()
        for msg in instance.messages:
            subject, files_produced = instance.process_email(msg)
            summary = instance.create_summary(files_produced)
            commit_id = instance.make_commit(subject, summary)

            print("%s: %s" % (commit_id, subject))
            for s in summary:
                p = s.split(':')
                print("%s -> %s (%s)" % (p[0], p[1], p[2]))

