#!/usr/bin/env python3

import unittest
import mailbox
from convert import mbox_to_git

class Testmbox_to_git(unittest.TestCase):
    def setUp(self):
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

if __name__ == '__main__':
    unittest.main()
