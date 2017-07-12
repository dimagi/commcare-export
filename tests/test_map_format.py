# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import unittest

from commcare_export.map_format import parse_template
from commcare_export.minilinq import Apply, Reference, Literal


class TestMapFormats(unittest.TestCase):
    def test_parse_template_no_args(self):
        expected = Apply(Reference('template'), Literal('my name is {}'), Reference('form.question1'))
        assert parse_template(Reference('form.question1'), 'template(my name is {})') == expected

    def test_parse_template_args(self):
        expected = Apply(Reference('template'), Literal('my name is {}'), Reference('form.question2'))
        assert parse_template('form.question1', 'template(my name is {}, form.question2)') == expected

    def test_parse_template_no_template(self):
        expected = Literal('Error: template function requires the format template: template()')
        assert parse_template('form.question1', 'template()') == expected
