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
import shlex

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

        subprocess.run(shlex.split('git init'),
                       cwd=self.repodir,
                       stdout=subprocess.DEVNULL)

        if encrypted:
            commands = [ 'git secret init',
                         'git add .',
                         'git commit -m "initializing git-secret module"' ]

            for c in commands:
                subprocess.call(shlex.split(c),
                                cwd=self.repodir,
                                stdout=subprocess.DEVNULL)

        from getpass import getuser
        self.set_user(getuser(), "%s@local" % getuser())

    def tell_secret(self, email):
        commands = [ 'git secret tell %s' % email,
                     'git add .',
                     'git commit -m "adding %s gpg identity"' % email ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

    def set_user(self, user, email):
        commands = [ 'git config user.name "%s"' % user,
                     'git config user.email "%s"' % email ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir)

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
        commands = [ 'git add .',
                     'git commit -m "%s" -m "%s"' % (subject, '\n'.join(summary)) ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)
        return self.head_id

    def make_secret_commit(self, subject, summary):
        ignored_files = []
        added_files = ['git add .gitignore', 'git add .gitsecret/paths/mapping.cfg']
        encrypted_summary = []
        with open(os.path.join(self.repodir, '.gitignore'), 'a') as gi:
            for s in summary:
                orig_name = s.split(':')[0]
                ignored_files.append("git secret add %s" % orig_name)
                added_files.append("git add %s.secret" % orig_name)
                encrypted_summary.append(s.replace(':', '.secret:', 1))
                gi.write("%s\n" % orig_name)

        for ifile in ignored_files:
            subprocess.run(shlex.split(ifile),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)

        subprocess.run(shlex.split('git secret hide -d'),
                       cwd=self.repodir,
                       stdout=subprocess.DEVNULL)

        for afile in added_files:
            subprocess.run(shlex.split(afile),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)

        command = 'git commit -m "%s" -m "%s"' % (subject,
                                                  '\n'.join(encrypted_summary))
        subprocess.run(shlex.split(command),
                       cwd=self.repodir,
                       stdout=subprocess.DEVNULL)

        return self.head_id

    @property
    def head_id(self):
        cmp_proc = subprocess.run(shlex.split('git rev-parse HEAD'),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,
                                  text=True)
        if cmp_proc.returncode == 128:
            return None
        else:
            return cmp_proc.stdout.strip()

    @property
    def commit_count(self):
        try:
            cmp_proc = subprocess.run(shlex.split('git rev-list --count HEAD'),
                                      cwd=self.repodir,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL,
                                      text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return 0
        else:
            return int(cmp_proc.stdout.strip()) if cmp_proc.stdout else 0

    @property
    def clean(self):
        cmp_proc = subprocess.run(shlex.split('git status --porcelain'),
                                  cwd=self.repodir,
                                  capture_output=True,
                                  text=True)
        return not bool(cmp_proc.stdout)

    def get_commit_of_file(self, fn):
        cmp_proc = subprocess.run(shlex.split('git rev-list -1 HEAD %s' % fn),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  text=True)
        return cmp_proc.stdout.strip()

    def get_commit_filelist(self, commit):
        command = 'git show --no-commit-id --name-only -r %s' % commit
        cmp_proc = subprocess.run(shlex.split(command),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,
                                  text=True)
        line_output = cmp_proc.stdout.split('\n')
        
        retval = []
        for line in line_output:
            split = line.split(' ')
            if len(split[0])==6 and len(split[1])==40 and split[0]=='commit': break
            retval.append(line)
        return retval

    def create_tarball(self):
        command = "git show --no-commit-id --name-only -r %s" % self.head_id
        show_process = subprocess.run(shlex.split(command),
                                      cwd=self.repodir,
                                      stdout=subprocess.PIPE,
                                      text=True)

        files = []
        for line in show_process.stdout.split('\n'):
            if line.startswith('commit '):
                break
            else:
                files.append(line)

        script_path=os.path.dirname(os.path.realpath(__file__))
        tarball_fp=os.path.join(script_path, 'commit.tar')

        import tarfile
        tar = tarfile.open(tarball_fp, 'w')
        for f in files:
            added_filepath = os.path.join(self.repodir, f)
            tar.add(added_filepath, arcname=f)
        tar.close()
        return tarball_fp

if __name__ == '__main__':
    with mbox_to_git('mbox.sample') as instance:
        instance.init_repo()
        for msg in instance.messages:
            subject, files_produced = instance.process_email(msg)
            summary = instance.create_summary(files_produced)
            commit_id = instance.make_commit(subject, summary)

            print("%s: %s" % (commit_id, subject))
            for s in summary:
                p = s.split(':')
                print("%s -> %s (%s)" % (p[0], p[1], p[2]))

