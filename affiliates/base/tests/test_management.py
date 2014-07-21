import sys

from nose.tools import eq_

from affiliates.base.management.commands import QuietCommand
from affiliates.base.tests import TestCase


class MockStdout(object):
    def __init__(self):
        self.buffer = []

    def write(self, output):
        self.buffer.append(output)


class QuietCommandTests(TestCase):
    def setUp(self):
        self.old_stdout = sys.stdout
        sys.stdout = MockStdout()

    def tearDown(self):
        sys.stdout = self.old_stdout

    def test_quiet_output(self):
        """If quiet is passed as an argument, do not output text."""
        class QuietTestCommand(QuietCommand):
            def handle_quiet(self, *args, **kwargs):
                self.output('test string')

        command = QuietTestCommand()
        command.handle(quiet=True)
        eq_(sys.stdout.buffer, [])

        command.handle(quiet=False)
        eq_(sys.stdout.buffer, ['test string', '\n'])

    def test_output_format(self):
        """
        Any arguments to output should be used as string formatting
        arguments.
        """
        class QuietTestCommand(QuietCommand):
            def handle_quiet(self, *args, **kwargs):
                self.output('foo {0} baz {biz}'.format('bar', biz='bonk'))

        command = QuietTestCommand()
        command.handle(quiet=False)
        eq_(sys.stdout.buffer, ['foo bar baz bonk', '\n'])
