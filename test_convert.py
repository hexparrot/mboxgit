#!/usr/bin/env python3

import unittest
import os
from convert import mbox_to_git

class Testmbox_to_git(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_accepts_mailbox_filepath(self):
        with self.assertRaises(TypeError):
            instance = mbox_to_git()

        with self.assertRaises(RuntimeError):
            instance = mbox_to_git('/')
        with self.assertRaises(RuntimeError):
            instance = mbox_to_git('/home')

        instance = mbox_to_git('pi')
        self.assertEqual(instance.mbox_fp, 'pi')

if __name__ == '__main__':
    unittest.main()
