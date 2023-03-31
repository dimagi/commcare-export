import unittest

from commcare_export.map_format import parse_function_arg, parse_template
from commcare_export.minilinq import Apply, Literal, Reference


class TestMapFormats(unittest.TestCase):

    def test_parse_template_no_args(self):
        expected = Apply(
            Reference('template'), Literal('my name is {}'),
            Reference('form.question1')
        )
        assert parse_template(
            Reference('form.question1'), 'template(my name is {})'
        ) == expected

    def test_parse_template_args(self):
        expected = Apply(
            Reference('template'), Literal('my name is {}'),
            Reference('form.question2')
        )
        assert parse_template(
            'form.question1', 'template(my name is {}, form.question2)'
        ) == expected

    def test_parse_template_args_long(self):
        expected = Apply(
            Reference('template'),
            Literal('https://www.commcarehq.org/a/{}/reports/form_data/{}/'),
            Reference('$.domain'),
            Reference('$.id'),
        )
        assert parse_template(
            'form.id',

            'template(https://www.commcarehq.org/a/{}/reports/form_data/{}/, '
            '$.domain, $.id)'
        ) == expected

    def test_parse_template_no_template(self):
        expected = Literal(
            'Error: template function requires the format template: template()'
        )
        assert parse_template('form.question1', 'template()') == expected

    def test_parse_function_arg_with_brackets(self):
        value_returned = parse_function_arg(
            'selected', 'selected(Other_(Specify))'
        )
        assert value_returned == 'Other_(Specify)'

    def test_parse_function_arg_empty_returns(self):
        value_returned = parse_function_arg('selected', 'selected()')
        assert value_returned == ''
