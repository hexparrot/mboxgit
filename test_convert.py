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
            self.assertEqual(len(instance.messages), 2)

    def test_create_gitrepo_dir(self):
        self.assertFalse(os.path.exists(REPO_FP))
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, REPO_FP)
        self.assertTrue(os.path.exists(REPO_FP))
        shutil.rmtree(REPO_FP)

        self.assertFalse(os.path.exists('mboxrepo'))
        with mbox_to_git(MBOX_FP, 'mboxrepo') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo')
        self.assertTrue(os.path.exists('mboxrepo'))
        shutil.rmtree('mboxrepo')

        self.assertFalse(os.path.exists('mboxrepo2'))
        with mbox_to_git(MBOX_FP, 'mboxrepo2') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo2')
        self.assertTrue(os.path.exists('mboxrepo2'))
        shutil.rmtree('mboxrepo2')

    def test_init_git_repo(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.git')))
            with self.assertRaises(RuntimeError):
                instance.init_repo()
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.git')))

    def test_create_mkstemp(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            files_produced = instance.process_email(instance.messages[0])
            self.assertEqual(len(files_produced), 1) #just body

            fn_on_disk, fn_base, fn_in_summary = files_produced[0]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'body')

            files_produced = instance.process_email(instance.messages[1])
            self.assertEqual(len(files_produced), 2) #body and attachment

            fn_on_disk, fn_base, fn_in_summary = files_produced[0]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'body')

            fn_on_disk, fn_base, fn_in_summary = files_produced[1]
            self.assertTrue(os.path.isfile(fn_on_disk))
            self.assertEqual(fn_in_summary, 'rsakey.pub')

    def test_fill_mkstemp(self):
        with mbox_to_git(MBOX_FP) as instance:
            instance.init_repo()
            files_produced = instance.process_email(instance.messages[0])

            fn_on_disk, fn_base, fn_in_summary = files_produced[0]
            self.assertEqual(os.path.getsize(fn_on_disk), 34)

            files_produced = instance.process_email(instance.messages[1])

            fn_on_disk, fn_base, fn_in_summary = files_produced[0]
            self.assertEqual(os.path.getsize(fn_on_disk), 23)
            fn_on_disk, fn_base, fn_in_summary = files_produced[1]
            self.assertEqual(os.path.getsize(fn_on_disk), 763)

if __name__ == '__main__':
    unittest.main()
