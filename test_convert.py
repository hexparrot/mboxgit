#!/usr/bin/env python3

import unittest
import mailbox
import shutil
import os
from convert import mbox_to_git

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

        with mbox_to_git('pi') as instance:
            self.assertEqual(instance.mbox_fp, 'pi')

    def test_mbox_context_manager(self):
        with mbox_to_git('pi') as instance:
            pass

    # commented out because this arrangement doesn't close the mbox after raising
    #def test_ensure_mailbox_locks(self):
    #    with mbox_to_git('pi') as instance:
    #        with self.assertRaises(mailbox.ExternalClashError):
    #            with mbox_to_git('pi') as instance2:
    #                pass

    def test_identifies_correct_message_count(self):
        with mbox_to_git('pi') as instance:
            self.assertEqual(len(instance.messages), 2)

    def test_create_gitrepo_dir(self):
        self.assertFalse(os.path.exists('mboxrepo'))
        with mbox_to_git('pi') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo')
        self.assertTrue(os.path.exists('mboxrepo'))
        shutil.rmtree('mboxrepo')

        self.assertFalse(os.path.exists('mboxrepo'))
        with mbox_to_git('pi', 'mboxrepo') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo')
        self.assertTrue(os.path.exists('mboxrepo'))
        shutil.rmtree('mboxrepo')

        self.assertFalse(os.path.exists('mboxrepo2'))
        with mbox_to_git('pi', 'mboxrepo2') as instance:
            instance.init_repo()
            self.assertEqual(instance.repodir, 'mboxrepo2')
        self.assertTrue(os.path.exists('mboxrepo2'))
        shutil.rmtree('mboxrepo2')

    def test_init_git_repo(self):
        with mbox_to_git('pi') as instance:
            instance.init_repo()
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.git')))
            with self.assertRaises(RuntimeError):
                instance.init_repo()
            self.assertTrue(os.path.exists(os.path.join(instance.repodir, '.git')))

if __name__ == '__main__':
    unittest.main()
