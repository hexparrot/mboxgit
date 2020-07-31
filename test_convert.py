#!/usr/bin/env python3

import unittest
import mailbox
import shutil
import os
from convert import mbox_to_git

MBOX_FP = 'pi'
REPO_FP = 'mboxrepo'

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
    #    with mbox_to_git('pi') as instance:
    #        with self.assertRaises(mailbox.ExternalClashError):
    #            with mbox_to_git('pi') as instance2:
    #                pass

    def test_identifies_correct_message_count(self):
        with mbox_to_git(MBOX_FP) as instance:
            self.assertEqual(len(instance.messages), 3)

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
            instance.init_repo()
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.git')))

    def test_create_mkstemp(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[0])
            self.assertEqual(len(files_produced), 1) #just body

            fn_on_disk, fn_in_summary, fsize = files_produced[0]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'body')

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
            instance.init_repo()
            config.read(os.path.join(REPO_FP, '.git', 'config'))
            self.assertEqual(config['user']['name'], MBOX_FP)
            self.assertEqual(config['user']['email'], "%s@local" % MBOX_FP)

            instance.set_user('will', 'will@bear.home')
            config.read(os.path.join(REPO_FP, '.git', 'config'))
            self.assertEqual(config['user']['name'], 'will')
            self.assertEqual(config['user']['email'], 'will@bear.home')

    def test_create_summary(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()

            subject, files_produced = instance.process_email(instance.messages[0])
            summary = instance.create_summary(files_produced)

            self.assertEqual(len(summary), len(files_produced))
            self.assertEqual(len(summary), 1)
            split_up = summary[0].split(':')
            self.assertTrue(4 <= len(split_up[0]) <= 8) # length variable (def min: 4)
            self.assertEqual(split_up[1], 'body')
            self.assertEqual(split_up[2], '34')

    def test_make_commit(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[0])
            summary = instance.create_summary(files_produced)
            short_commit = instance.make_commit(subject, summary)
            self.assertTrue(len(short_commit) >= 5)
            self.assertIsInstance(short_commit, str)

    def test_init_repo_graceful_reuse(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            instance.init_repo(abort_if_exists=False)
            with self.assertRaises(RuntimeError):
                instance.init_repo(abort_if_exists=True)

    def test_get_git_head_commit(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            subject, files_produced = instance.process_email(instance.messages[0])
            summary = instance.create_summary(files_produced)
            self.assertIsNone(instance.head_id)
            instance.make_commit(subject, summary)
            short_commit = instance.head_id
            self.assertTrue(len(short_commit) >= 5)
            self.assertIsInstance(short_commit, str)

if __name__ == '__main__':
    unittest.main()
