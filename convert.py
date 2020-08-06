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
            # put a lock on the mailbox preventing external edits
            # until this object is closed / full script execution
            self.mailbox.lock()
            # emails from mbox_path are IMMEDIATELY read and copied
            # to this object; this makes it potentially one of the
            # longest calls and least protected from untesetd email
            # TODO: find email structure that mailbox obj raises for
            self.messages = [msg for msg in self.mailbox]

    def __enter__(self):
        return self # boilerplate for allowing with/as context mgr

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

        # TODO: determine way these commands do not need to run,
        #       e.g., production use when repo always will exist on instantiation.
        subprocess.run(shlex.split('git init'),
                       cwd=self.repodir,
                       stdout=subprocess.DEVNULL)

        # TODO: this could cause noise on repeats (although otherwise not truly impactful)
        if encrypted:
            commands = [ 'git secret init',
                         'git add .',
                         'git commit -m "initializing git-secret module"' ]

            for c in commands:
                subprocess.call(shlex.split(c),
                                cwd=self.repodir,
                                stdout=subprocess.DEVNULL)

        # TODO: this will also need to eventually accept user input
        from getpass import getuser
        self.set_user(getuser(), "%s@local" % getuser())

    def tell_secret(self, email):
        """ Accepts an email address signifying the GPG --list-keys entry
            intending to be a user of this git repo. In server deployments,
            this means possession of pubkey imported into GPG.
        """
        # TODO: accept filepath to a key or potentially generate
        commands = [ 'git secret tell %s' % email,
                     'git add .',
                     'git commit -m "adding %s gpg identity"' % email ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

    def set_user(self, user, email):
        """ Accepts user and email from user and sets in git as author.
            No functionality will work if this doesn't satisfy git.
        """
        # TODO: Protected from injection via shlex, but otherwise could
        #       greatly benefit from sanitization and bad input detection
        commands = [ 'git config user.name "%s"' % user,
                     'git config user.email "%s"' % email ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir)

    def process_email(self, email):
        """ Processes individual emails in mbox-style box r/o.
            Identifies multipart emails and splits body and attachments
            all into separate files implemented with mkstemp.
        """
        def fill_file(data, encoding='ascii'):
            """ Receives data BASE64/ASCII and writes it to "temporary" file.
                Returns filedescriptor, path, and size of resultant file.
            """
            ascii_as_bytes = data.encode('ascii')
            if encoding == 'base64':
                import base64
                message_bytes = base64.b64decode(ascii_as_bytes)
            else:
                message_bytes = ascii_as_bytes

            import tempfile
            # create file directly in repopath, does not unlink
            t_filedesc, t_filepath = tempfile.mkstemp(prefix='', dir=self.repodir)
            open_file = open(t_filepath, 'w+b')
            open_file.write(message_bytes)
            open_file.flush()
            open_file.close()

            return (t_filedesc, t_filepath, len(message_bytes))

        processed_parts = []
        split_parts = email.get_payload()
        subject = email.get('subject')

        if isinstance(split_parts, list): # this is a multipart email
            for p in split_parts:
                final_filename = p.get_filename('body') # fallback if multipart, but not an attachment
                encoding = p.get('Content-Transfer-Encoding')
                tmp_filedesc, tmp_filepath, tmp_size = fill_file(p.get_payload(), encoding)
                processed_parts.append( (tmp_filepath, final_filename, tmp_size) )
        else: #single part email means content provided directly as string
            final_filename = 'body'
            tmp_filedesc, tmp_filepath, tmp_size = fill_file(split_parts)
            processed_parts.append( (tmp_filepath, final_filename, tmp_size) )

        return (subject, processed_parts)

    def create_summary(self, processed_parts):
        """ Returns list of [name saved on disk:name when retrieved:size of part] """
        summary = []
        for fp, final_name, fsize in processed_parts:
            summary.append("%s:%s:%i" % (os.path.basename(fp), final_name, fsize))
        return summary

    def make_commit(self, subject, summary):
        """ Receives subject name and file summary and commits it to git log """
        commands = [ 'git add .',
                     'git commit -m "%s" -m "%s"' % (subject, '\n'.join(summary)) ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)
        return self.head_id

    def make_secret_commit(self, subject, summary):
        """ Creates a new commit in the git tree including
            all attachments, the body text uploaded as 'body',
            and the git log header matching the email subject.

            The files will have .secret affixed to them,
            becoming their new file identity, signifying that
            a private key would be required to decrypt the key
            even after attaining the file.
        """
        git_secret_add_cmds = []
        git_add_cmds = ['git add .gitignore', 'git add .gitsecret/paths/mapping.cfg']
        revised_summary = []

        with open(os.path.join(self.repodir, '.gitignore'), 'a') as gi:
            for s in summary:
                rnd_name = s.split(':')[0]
                # git secret add does two things:
                # 1) encrypts FILE and produces FILE.secret
                git_secret_add_cmds.append("git secret add %s" % rnd_name)
                # 2) requires FILE to be added to .gitignore
                gi.write("%s\n" % rnd_name)

                # git add the encrypted file with added suffix
                git_add_cmds.append("git add %s.secret" % rnd_name)
                # ensure the git commit longform contains the fn update
                revised_summary.append(s.replace(':', '.secret:', 1))

        for cmd in git_secret_add_cmds:
            subprocess.run(shlex.split(cmd),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)

        # -F required to do encryption of only newly added files, instead of all
        subprocess.run(shlex.split('git secret hide -F -d'),
                       cwd=self.repodir,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

        for cmd in git_add_cmds:
            subprocess.run(shlex.split(cmd),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)

        cmd = 'git commit -m "%s" -m "%s"' % (subject,
                                             '\n'.join(revised_summary))
        subprocess.run(shlex.split(cmd),
                       cwd=self.repodir,
                       stdout=subprocess.DEVNULL)

        return self.head_id

    @property
    def head_id(self):
        """ Returns commit hash of the current HEAD """
        cmp_proc = subprocess.run(shlex.split('git rev-parse HEAD'),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,
                                  text=True)
        if cmp_proc.returncode == 128:
            return None # triggers on dir not yet git init-ed
        else:
            return cmp_proc.stdout.strip()

    @property
    def commit_count(self):
        """ Returns number of commits in current branch """
        try:
            cmp_proc = subprocess.run(shlex.split('git rev-list --count HEAD'),
                                      cwd=self.repodir,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL,
                                      text=True)
        except FileNotFoundError:
            return 0
        else:
            return int(cmp_proc.stdout.strip()) if cmp_proc.stdout else 0

    @property
    def clean(self):
        """ Returns bool of whether working tree is clean """
        cmp_proc = subprocess.run(shlex.split('git status --porcelain'),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  text=True)
        return not bool(cmp_proc.stdout)

    def get_commit_of_file(self, fn):
        """ Traverses commits in reverse for first match of filename fn
            and returns commit hash
        """
        cmp_proc = subprocess.run(shlex.split('git rev-list -1 HEAD %s' % fn),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  text=True)
        return cmp_proc.stdout.strip()

    def get_commit_filelist(self, commit):
        """ Construct a list of all files relevant to given commit hash """
        command = 'git show --no-commit-id --name-only -r %s' % commit
        cmp_proc = subprocess.run(shlex.split(command),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  text=True)
        line_output = cmp_proc.stdout.split('\n')
        
        retval = []
        for line in line_output:
            split = line.split(' ')
            # expecting a line 'commit ab324298798b ...'
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

        renames = {}
        for line in show_process.stdout.split('\n'):
            if line.count(':') == 2:
                rnd, orig, size = line.split(':')
                rnd = rnd.strip()
                if rnd in files:
                    renames[rnd] = orig

        script_path=os.path.dirname(os.path.realpath(__file__))
        tarball_fp=os.path.join(script_path, 'commit.tar')

        import tarfile
        tar = tarfile.open(tarball_fp, 'w')
        for random_name, original_name in renames.items():
            added_filepath = os.path.join(self.repodir, random_name)
            tar.add(added_filepath, arcname=original_name)
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

