"""4.24.1: runtime/weakened_tests.py reads the YAML forms it took for something else. An unquoted != or * is text, not a tag
or an alias; a block scalar (where: |) keeps its text, so a change in it is seen; enabled and severity written as an
expression the script cannot read are reported as a changed setting instead of being taken for unchanged."""
import unittest

import test_weakened_tests

SCHEMA = test_weakened_tests.SCHEMA
PROJECT = test_weakened_tests.DBT_PROJECT
CONFIG = '                severity: error\n'


class YamlFormsTests(test_weakened_tests.Base):
    def facts(self, before, after):
        repo = self.repo({'dbt_project.yml': PROJECT, 'models/schema.yml': before, 'models/orders.sql': 'select 1\n'})
        repo.write({'models/schema.yml': after})
        code, out = repo.run()
        return [(f['kind'], f.get('test')) for f in out['facts']], out['files_unreadable']

    def test_an_unquoted_comparison_or_star_is_text(self):
        text = SCHEMA.replace('error_if: ">0"', 'error_if: !=0').replace('    columns:\n', '    description: *draft* model, amount*2 & more\n    columns:\n', 1)
        self.assertEqual(self.facts(text, text.replace('          - unique\n', '', 1)), ([('test_removed', 'orders.order_id.unique')], []))
        module = test_weakened_tests.load_module()
        self.assertEqual(module.parse_yaml('a: !=0\nb: *.sql\nc: x != y\nd: 2 * 3\n'), {'a': '!=0', 'b': '*.sql', 'c': 'x != y', 'd': '2 * 3'})
        for anchored in ('a: &x 1\n', 'a: *x\n', 'a: !!str 1\n', 'a: !custom 1\n', 'a: [*x]\n'):
            with self.assertRaises(module.YamlError, msg=anchored):
                module.parse_yaml(anchored)

    def test_a_block_scalar_keeps_its_text(self):
        module = test_weakened_tests.load_module()
        parsed = module.parse_yaml('where: |\n  amount > 0  # kept: SQL, not a YAML comment\n  and tags[0] = \'x\'\n\n  and a != b\nnext: 1\n'
                                   'items:\n  - rows: |\n      id,amount\n      1,10\n  - >-\n    folded\n    text\n')
        self.assertEqual(parsed['where'], "amount > 0  # kept: SQL, not a YAML comment\nand tags[0] = 'x'\n\nand a != b")
        self.assertEqual(parsed['next'], 1 if False else '1')
        self.assertEqual(parsed['items'], [{'rows': 'id,amount\n1,10'}, 'folded text'])

    def test_a_change_inside_a_block_scalar_is_seen(self):
        before = SCHEMA.replace(CONFIG, CONFIG + '                where: |\n                  amount > 0\n                  and status = \'paid\'\n', 1)
        after = before.replace("and status = 'paid'", "and status = 'paid' and 1 = 0")
        self.assertEqual(self.facts(before, after), ([('assertion_changed', 'orders.amount.not_null')], []))
        self.assertEqual(self.facts(before, before.replace('          - unique\n', '', 1)), ([('test_removed', 'orders.order_id.unique')], []))

    def test_enabled_or_severity_the_script_cannot_read_is_a_changed_setting(self):
        for added in ('                enabled: "{{ false }}"\n', '                enabled: "{{ var(\'run_checks\') }}"\n'):
            self.assertEqual(self.facts(SCHEMA, SCHEMA.replace(CONFIG, CONFIG + added, 1)), ([('assertion_changed', 'orders.amount.not_null')], []), added)
        self.assertEqual(self.facts(SCHEMA, SCHEMA.replace('severity: error', 'severity: "{{ \'warn\' }}"', 1)),
                         ([('assertion_changed', 'orders.amount.not_null')], []))
        # What the script reads keeps its own verdict, and what did not change says nothing.
        self.assertEqual(self.facts(SCHEMA, SCHEMA.replace(CONFIG, CONFIG + '                enabled: false\n', 1))[0], [('test_disabled', 'orders.amount.not_null')])
        self.assertEqual(self.facts(SCHEMA, SCHEMA.replace('severity: error', 'severity: warn', 1))[0], [('severity_lowered', 'orders.amount.not_null')])
        self.assertEqual(self.facts(SCHEMA, SCHEMA.replace(CONFIG, CONFIG + '                enabled: true\n', 1)), ([], []))
        jinja = SCHEMA.replace(CONFIG, CONFIG + '                enabled: "{{ false }}"\n', 1)
        self.assertEqual(self.facts(jinja, jinja.replace('          - unique\n', '', 1)), ([('test_removed', 'orders.order_id.unique')], []))


if __name__ == '__main__':
    unittest.main()
