#!/usr/bin/env python3

import unittest
import mailbox
import shutil
import os
from convert import mbox_to_git

MBOX_FP = 'mbox.sample'
REPO_FP = 'mboxrepo'
GPG_EMAIL = 'wdchromium@gmail.com'

class Testmbox_to_git(unittest.TestCase):
    def setUp(self):
        try:
            shutil.rmtree('mboxrepo')
        except FileNotFoundError:
            pass

    def tearDown(self):
        pass

    def test_accepts_mailbox_filepath(self):
        with self.assertRaises(TypeError):
            with mbox_to_git() as instance:
                pass

        with self.assertRaises(RuntimeError):
            with mbox_to_git('/') as instance:
                pass
        with self.assertRaises(RuntimeError):
            with mbox_to_git('/home') as instance:
                pass

        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(instance.mbox_fp, MBOX_FP)

    def test_mbox_context_manager(self):
        with mbox_to_git(MBOX_FP) as instance:
            pass

    # commented out because this arrangement doesn't close the mbox after raising
    #def test_ensure_mailbox_locks(self):
    #    with mbox_to_git(MBOX_FP) as instance:
    #        with self.assertRaises(mailbox.ExternalClashError):
    #            with mbox_to_git(MBOX_FP) as instance2:
    #                pass

    def test_identifies_correct_message_count(self):
        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(len(instance.messages), 4)

    def test_create_gitrepo_dir(self):
        self.assertFalse(os.path.exists(REPO_FP))
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, REPO_FP)
        self.assertTrue(os.path.exists(REPO_FP))
        shutil.rmtree(REPO_FP)

        self.assertFalse(os.path.exists('mboxrepo'))
        with mbox_to_git(MBOX_FP, repodir='mboxrepo') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo')
        self.assertTrue(os.path.exists('mboxrepo'))
        shutil.rmtree('mboxrepo')

        self.assertFalse(os.path.exists('mboxrepo2'))
        with mbox_to_git(MBOX_FP, repodir='mboxrepo2') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo2')
        self.assertTrue(os.path.exists('mboxrepo2'))
        shutil.rmtree('mboxrepo2')

    def test_init_git_repo(self):
        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(instance.commit_count, 0)
            instance.init_repo()
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.git')))
            self.assertEqual(instance.commit_count, 0)
            self.assertTrue(instance.clean)

    def test_create_mkstemp(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[0])
            self.assertEqual(len(files_produced), 1) #just body

            fn_on_disk, fn_in_summary, fsize = files_produced[0]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'body')
            os.unlink(fn_on_disk)

            subject, files_produced = instance.process_email(instance.messages[1])
            self.assertEqual(len(files_produced), 2) #body and attachment

            fn_on_disk, fn_in_summary, fsize = files_produced[0]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'body')

            fn_on_disk, fn_in_summary, fsize = files_produced[1]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'rsakey.pub')

    def test_fill_mkstemp(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[0])

            fn_on_disk, fn_in_summary, fsize = files_produced[0]
            self.assertEqual(os.path.getsize(fn_on_disk), 34)
            self.assertEqual(os.path.getsize(fn_on_disk), fsize)
            os.unlink(fn_on_disk)

            subject, files_produced = instance.process_email(instance.messages[1])

            fn_on_disk, fn_in_summary, fsize = files_produced[0]
            self.assertEqual(os.path.getsize(fn_on_disk), 23)
            self.assertEqual(os.path.getsize(fn_on_disk), fsize)

            fn_on_disk, fn_in_summary, fsize = files_produced[1]
            self.assertEqual(os.path.getsize(fn_on_disk), 563)
            self.assertEqual(os.path.getsize(fn_on_disk), fsize)

    def test_fill_binary_attachment(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[2])

            fn_on_disk, fn_in_summary, fsize = files_produced[0]
            self.assertEqual(os.path.getsize(fn_on_disk), 3)
            self.assertEqual(os.path.getsize(fn_on_disk), fsize)

            fn_on_disk, fn_in_summary, fsize = files_produced[1]
            self.assertEqual(os.path.getsize(fn_on_disk), 7716)
            self.assertEqual(os.path.getsize(fn_on_disk), fsize)

    def test_set_git_user(self):
        import configparser
        config = configparser.ConfigParser()

        with mbox_to_git(MBOX_FP) as instance:
            from getpass import getuser
            instance.init_repo()
            config.read(os.path.join(REPO_FP, '.git', 'config'))
            self.assertEqual(config['user']['name'], getuser())
            self.assertEqual(config['user']['email'], "%s@local" % getuser())

            instance.set_user('will', 'will@bear.home')
            config.read(os.path.join(REPO_FP, '.git', 'config'))
            self.assertEqual(config['user']['name'], 'will')
            self.assertEqual(config['user']['email'], 'will@bear.home')

    def test_make_commit(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            self.assertTrue(instance.clean)
            subject, files_produced = instance.process_email(instance.messages[0])
            self.assertEqual(instance.commit_count, 0)
            short_commit = instance.make_commit(subject, files_produced)
            self.assertTrue(len(short_commit) == 40)
            self.assertIsInstance(short_commit, str)
            self.assertEqual(instance.commit_count, 1)
            self.assertTrue(instance.clean)

    def test_init_repo_graceful_reuse(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            with self.assertRaises(FileExistsError):
                instance.init_repo()
            instance.init_repo(encrypted=True)
            with self.assertRaises(FileExistsError):
                instance.init_repo(encrypted=True)

    def test_get_git_head_commit(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[0])
            self.assertIsNone(instance.head_id)
            instance.make_commit(subject, files_produced)
            head_commit = instance.head_id
            self.assertTrue(len(head_commit) == 40)
            self.assertIsInstance(head_commit, str)

    def test_get_commit_by_stored_filename(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            subject, files_produced = instance.process_email(instance.messages[1])
            created_commit = instance.make_commit(subject, files_produced)
            
            rnd_name, orig_name, _ = files_produced[1]
            rnd_name = os.path.basename(rnd_name) # take off directory components
            self.assertEqual(orig_name, 'rsakey.pub')
            matching_commit = instance.get_commit_of_file(rnd_name)
            self.assertTrue(len(matching_commit) == 40)
            self.assertIsInstance(matching_commit, str)
            self.assertEqual(matching_commit, created_commit)

    def test_get_commit_filelist(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            subject, files_produced = instance.process_email(instance.messages[1])
            commit = instance.make_commit(subject, files_produced)
            
            rnd_name, orig_name, _ = files_produced[0]
            rnd_name = os.path.basename(rnd_name) # take off directory components
            matching_commit = instance.get_commit_of_file(rnd_name)
            file_list = instance.get_commit_filelist(matching_commit)
            self.assertTrue(rnd_name in file_list)
            self.assertEqual(len(file_list), 2)

    def test_init_secret(self):
        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(instance.commit_count, 0)
            instance.init_repo(encrypted=True)
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.gitsecret')))
            self.assertEqual(instance.commit_count, 1)
            self.assertTrue(instance.clean)

    def test_tell_secret(self):
        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(instance.commit_count, 0)
            instance.init_repo(encrypted=True)
            self.assertEqual(instance.commit_count, 1)
            instance.tell_secret(GPG_EMAIL)
            self.assertEqual(instance.commit_count, 2)
            gitsecret_path = os.path.join(instance.repodir, '.gitsecret')
            self.assertTrue(os.path.isfile(os.path.join(gitsecret_path, 'keys', 'pubring.kbx')))
            self.assertTrue(os.path.isfile(os.path.join(gitsecret_path, 'keys', 'trustdb.gpg')))

    def test_make_secret(self):
        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(instance.commit_count, 0)
            instance.init_repo(encrypted=True)
            instance.tell_secret(GPG_EMAIL)
            self.assertTrue(instance.clean)

            subject, files_produced = instance.process_email(instance.messages[0])
            commit_count = instance.commit_count
            short_commit = instance.make_secret_commit(subject, files_produced)
            self.assertEqual(instance.commit_count, commit_count + 1)
            filename = os.path.basename(files_produced[0][0]) # take off directory components
            self.assertTrue(os.path.isfile(os.path.join(instance.repodir, filename + '.secret')))
            self.assertFalse(os.path.isfile(os.path.join(instance.repodir, filename)))
            self.assertTrue(instance.clean)

    def test_tree_clean(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            self.assertTrue(instance.clean)
            subject, files_produced = instance.process_email(instance.messages[0])
            self.assertFalse(instance.clean)
            commit = instance.make_commit(subject, files_produced)
            self.assertTrue(instance.clean)

    def test_create_tarball(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            for e in instance.messages:
                subject, files_produced = instance.process_email(e)
                commit = instance.make_commit(subject, files_produced)

                src_filenames = [s[1] for s in files_produced]
                renames = {}
                for rnd, orig, _ in files_produced:
                    renames[orig] = os.path.basename(rnd)

                file_created = instance.create_tarball()
                self.assertTrue(os.path.isfile(file_created))

                import tarfile

                self.assertTrue(tarfile.is_tarfile(file_created))
                with tarfile.TarFile(file_created, 'r') as tf:
                    self.assertEqual(set(tf.getnames()), set(src_filenames))
                    for m in tf.getmembers():
                        file_on_disk = os.path.join(instance.repodir, renames[m.name])
                        self.assertEqual(m.size, os.stat(file_on_disk).st_size)

    def test_create_tarball_encrypted(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo(encrypted=True)
            instance.tell_secret(GPG_EMAIL)

            for e in instance.messages:
                subject, files_produced = instance.process_email(e)
                commit = instance.make_secret_commit(subject, files_produced)

                src_filenames = [s[1] for s in files_produced]
                renames = {}
                for rnd, orig, _ in files_produced:
                    renames[orig] = os.path.basename(rnd) + '.secret'

                file_created = instance.create_tarball()
                self.assertTrue(os.path.isfile(file_created))

                import tarfile

                self.assertTrue(tarfile.is_tarfile(file_created))
                with tarfile.TarFile(file_created, 'r') as tf:
                    self.assertEqual(set(tf.getnames()), set(src_filenames))
                    for m in tf.getmembers():
                        file_on_disk = os.path.join(instance.repodir, renames[m.name])
                        self.assertEqual(m.size, os.stat(file_on_disk).st_size)
                os.unlink(file_created)

    def test_decorator_check_clean_before(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            try:
                subject, files_produced = instance.process_email(instance.messages[0])
            except ExceptionType:
                self.fail("this should not have thrown anything")

            with self.assertRaises(RuntimeError):
                subject, files_produced = instance.process_email(instance.messages[0])

    def test_decorator_check_clean_after(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            subject, files_produced = instance.process_email(instance.messages[0])

            with self.assertRaises(RuntimeError):
                subject, files_produced = instance.process_email(instance.messages[0])

            try:
                commit = instance.make_commit(subject, files_produced)
            except ExceptionType:
                self.fail("this should not have thrown anything")

    def test_inbound_utf_encoding(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[3])
            short_commit = instance.make_commit(subject, files_produced)


if __name__ == '__main__':
    unittest.main()
