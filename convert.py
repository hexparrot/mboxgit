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

class Decorators(object):
    def check_clean_before(func):
        def decorated(self, *args, **kwargs):
            if not self.clean: raise RuntimeError('working tree not clean before operation; cannot continue')
            return func(self, *args, **kwargs)
        return decorated
    
    def check_clean_after(func):
        def decorated(self, *args, **kwargs):
            retval = func(self, *args, **kwargs)
            if not self.clean: raise RuntimeError('working tree not clean after operation; cannot continue')
            return retval
        return decorated

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

    @Decorators.check_clean_after
    def init_repo(self,
                  encrypted=False):
        commands = ['git init']
        try:
            os.mkdir(self.repodir)
        except FileExistsError:
            if encrypted:
                if os.path.exists(os.path.join(self.repodir, '.gitsecret')):
                    raise FileExistsError("Cannot secret re-init a repo.")
            else:
                raise FileExistsError("Cannot re-init a repo.")

        if encrypted:
            commands.extend([ 'git secret init',
                              'git add .',
                              'git commit -m "initializing git-secret module"' ])

        for c in commands:
            subprocess.call(shlex.split(c),
                            cwd=self.repodir,
                            stdout=subprocess.DEVNULL)

        # TODO: this will also need to eventually accept user input
        from getpass import getuser
        self.set_user(getuser(), "%s@local" % getuser())

    @Decorators.check_clean_before
    @Decorators.check_clean_after
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

    @Decorators.check_clean_before
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

    @Decorators.check_clean_after
    def make_commit(self, subject, processed_parts):
        """ Receives subject name and processed message parts and commits it to git log """
        summary = []
        for fp, final_name, fsize in processed_parts:
            summary.append("%s:%s:%i" % (os.path.basename(fp), final_name, fsize))

        commands = [ 'git add .',
                     'git commit -m "%s" -m "%s"' % (subject, '\n'.join(summary)) ]

        for c in commands:
            subprocess.run(shlex.split(c),
                           cwd=self.repodir,
                           stdout=subprocess.DEVNULL)
        return self.head_id

    @Decorators.check_clean_after
    def make_secret_commit(self, subject, processed_parts):
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

        summary = []
        for fp, final_name, fsize in processed_parts:
            summary.append("%s:%s:%i" % (os.path.basename(fp), final_name, fsize))

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
        """ Create tarball containing files of only HEAD commit.
            Changing the head may be entirely unnecessary because
            all files are going to be named with mkstemp so there
            is no collision in that space. """
        command = "git show --no-commit-id --name-only -r %s" % self.head_id
        cmp_proc = subprocess.run(shlex.split(command),
                                  cwd=self.repodir,
                                  stdout=subprocess.PIPE,
                                  text=True)

        files = []
        # files are demarcated by 'commit abcdef1234...' line
        for line in cmp_proc.stdout.split('\n'):
            if line.startswith('commit '):
                break
            else:
                files.append(line)

        file_mapping = []
        # iterate stdout again to catch summary mapping below commit info
        # this allows us to return the human-expected name rather than the mkstep
        for line in cmp_proc.stdout.split('\n'):
            if line.count(':') == 2:
                rnd, orig, size = line.split(':')
                rnd = rnd.strip()
                if rnd in files: # if this line matches a known-file identified above
                    file_mapping.append( (rnd, orig) )

        script_path=os.path.dirname(os.path.realpath(__file__))
        # this file is created outside the repo tree, in the script path
        tarball_fp=os.path.join(script_path, 'commit.tar')

        import tarfile
        tar = tarfile.open(tarball_fp, 'w')
        for random_name, original_name in file_mapping:
            added_filepath = os.path.join(self.repodir, random_name)
            tar.add(added_filepath, arcname=original_name)
        tar.close()
        return tarball_fp

if __name__ == '__main__':
    with mbox_to_git('mbox.sample') as instance:
        try:
            instance.init_repo()
        except FileExistsError:
            pass

        for msg in instance.messages:
            subject, files_produced = instance.process_email(msg)
            commit_id = instance.make_commit(subject, files_produced)

            print("%s: %s" % (commit_id, subject))
            for path, fn, size in files_produced:
                print("%s -> %s (%s)" % (os.path.basename(path), fn, size))

