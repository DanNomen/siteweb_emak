# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDecadeStatement(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.Statement = cls.env['decade.statement']

    # ─────────────────────────────────────────────────────────────────────
    # Bornes de décade
    # ─────────────────────────────────────────────────────────────────────

    def test_decade_range_boundaries(self):
        # Décade 1 : 1 -> 10
        start, end, num = self.Statement._get_decade_range(date(2026, 3, 5))
        self.assertEqual((start, end, num), (date(2026, 3, 1), date(2026, 3, 10), 1))

        # Décade 2 : 11 -> 20
        start, end, num = self.Statement._get_decade_range(date(2026, 3, 15))
        self.assertEqual((start, end, num), (date(2026, 3, 11), date(2026, 3, 20), 2))

        # Décade 3 sur un mois de 31 jours
        start, end, num = self.Statement._get_decade_range(date(2026, 3, 25))
        self.assertEqual((start, end, num), (date(2026, 3, 21), date(2026, 3, 31), 3))

        # Décade 3 sur février non-bissextile (28 jours)
        start, end, num = self.Statement._get_decade_range(date(2026, 2, 25))
        self.assertEqual((start, end, num), (date(2026, 2, 21), date(2026, 2, 28), 3))

        # Décade 3 sur février bissextile (29 jours) — 2028 est bissextile
        start, end, num = self.Statement._get_decade_range(date(2028, 2, 25))
        self.assertEqual((start, end, num), (date(2028, 2, 21), date(2028, 2, 29), 3))

    def test_compute_period_matches_selection_string(self):
        # decade_number est stocké comme Selection ('1'/'2'/'3') : vérifie la conversion.
        start, end = self.Statement._compute_period(2026, 4, '2')
        self.assertEqual((start, end), (date(2026, 4, 11), date(2026, 4, 20)))

    # ─────────────────────────────────────────────────────────────────────
    # Génération des lignes
    # ─────────────────────────────────────────────────────────────────────

    def test_generate_lines_groups_by_partner(self):
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date=date(2026, 3, 5), amounts=[100],
        )
        invoice.action_post()

        statement = self.Statement.create({
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 10),
            'month_ref': date(2026, 3, 1),
            'decade_number': '1',
            'company_id': self.env.company.id,
        })
        statement.action_generate_lines()

        self.assertEqual(statement.state, 'ready')
        self.assertEqual(statement.client_count, 1)
        self.assertEqual(statement.line_ids.partner_id, self.partner_a)

    def test_regenerate_preserves_sent_lines(self):
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date=date(2026, 3, 5), amounts=[100],
        )
        invoice.action_post()

        statement = self.Statement.create({
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 10),
            'month_ref': date(2026, 3, 1),
            'decade_number': '1',
            'company_id': self.env.company.id,
        })
        statement.action_generate_lines()
        line = statement.line_ids
        line.email_sent = True

        # Régénérer ne doit pas supprimer/recréer la ligne déjà envoyée.
        statement.action_generate_lines()
        self.assertEqual(statement.line_ids, line)
        self.assertTrue(statement.line_ids.email_sent)

    def test_older_unpaid_invoice_carried_over_with_origin(self):
        """Une facture impayée de la décade 1 doit réapparaître dans le
        relevé de la décade 3, avec un renvoi vers le relevé d'origine."""
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date=date(2026, 3, 5), amounts=[100],
        )
        invoice.action_post()

        statement_1 = self.Statement.create({
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 10),
            'month_ref': date(2026, 3, 1),
            'decade_number': '1',
            'company_id': self.env.company.id,
        })
        statement_1.action_generate_lines()  # passe en 'ready'

        statement_3 = self.Statement.create({
            'date_start': date(2026, 3, 21),
            'date_end': date(2026, 3, 31),
            'month_ref': date(2026, 3, 1),
            'decade_number': '3',
            'company_id': self.env.company.id,
        })
        statement_3.action_generate_lines()

        line_3 = statement_3.line_ids
        self.assertIn(invoice, line_3.invoice_ids)
        origin_map = line_3.get_invoices_origin_map()
        self.assertEqual(origin_map.get(invoice.id), statement_1.name)

    def test_invoice_detail_synced_with_origin_statement(self):
        """decade.statement.line.invoice doit rester synchronisé avec
        invoice_ids et exposer le relevé d'origine en colonne."""
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date=date(2026, 3, 5), amounts=[100],
        )
        invoice.action_post()

        statement_1 = self.Statement.create({
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 10),
            'month_ref': date(2026, 3, 1),
            'decade_number': '1',
            'company_id': self.env.company.id,
        })
        statement_1.action_generate_lines()
        detail_1 = statement_1.line_ids.invoice_detail_ids
        self.assertEqual(detail_1.invoice_id, invoice)
        self.assertFalse(detail_1.origin_statement_id)  # première apparition
        self.assertTrue(detail_1.is_new_this_period)  # datée dans la décade 1

        statement_3 = self.Statement.create({
            'date_start': date(2026, 3, 21),
            'date_end': date(2026, 3, 31),
            'month_ref': date(2026, 3, 1),
            'decade_number': '3',
            'company_id': self.env.company.id,
        })
        statement_3.action_generate_lines()
        detail_3 = statement_3.line_ids.invoice_detail_ids
        self.assertEqual(detail_3.invoice_id, invoice)
        self.assertEqual(detail_3.origin_statement_id, statement_1)
        self.assertFalse(detail_3.is_new_this_period)  # reportée, pas datée dans la décade 3

        # Vue agrégée au niveau du relevé (tous clients confondus).
        self.assertEqual(statement_3.invoice_detail_ids, detail_3)

    def test_fully_paid_invoice_not_carried_over(self):
        """Une facture soldée ne doit plus apparaître dans les relevés suivants."""
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date=date(2026, 3, 5), amounts=[100],
        )
        invoice.action_post()
        self.assertEqual(invoice.payment_state, 'not_paid')

        # Règlement complet via l'assistant standard de paiement.
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({})
        payment_register._create_payments()
        self.assertEqual(invoice.payment_state, 'paid')

        statement_3 = self.Statement.create({
            'date_start': date(2026, 3, 21),
            'date_end': date(2026, 3, 31),
            'month_ref': date(2026, 3, 1),
            'decade_number': '3',
            'company_id': self.env.company.id,
        })
        with self.assertRaises(UserError):
            statement_3.action_generate_lines()

    # ─────────────────────────────────────────────────────────────────────
    # Cron : jours de bascule (contourne la dérive calendaire d'un intervalle
    # fixe de 10 jours, qui ne correspond pas à des mois de longueur variable)
    # ─────────────────────────────────────────────────────────────────────

    def test_closed_decade_on_trigger_days(self):
        # Le 11 -> décade 1 (1->10) du mois courant vient de finir
        self.assertEqual(
            self.Statement._get_closed_decade_for_date(date(2026, 3, 11)),
            (date(2026, 3, 1), date(2026, 3, 10), 1),
        )
        # Le 21 -> décade 2 (11->20) du mois courant vient de finir
        self.assertEqual(
            self.Statement._get_closed_decade_for_date(date(2026, 3, 21)),
            (date(2026, 3, 11), date(2026, 3, 20), 2),
        )
        # Le 1er -> décade 3 (21->fin) du mois PRÉCÉDENT vient de finir
        self.assertEqual(
            self.Statement._get_closed_decade_for_date(date(2026, 3, 1)),
            (date(2026, 2, 21), date(2026, 2, 28), 3),
        )
        # Passage d'année : 1er janvier -> décade 3 de décembre de l'année précédente
        self.assertEqual(
            self.Statement._get_closed_decade_for_date(date(2026, 1, 1)),
            (date(2025, 12, 21), date(2025, 12, 31), 3),
        )

    def test_closed_decade_returns_none_on_non_trigger_days(self):
        self.assertIsNone(self.Statement._get_closed_decade_for_date(date(2026, 3, 5)))
        self.assertIsNone(self.Statement._get_closed_decade_for_date(date(2026, 3, 15)))
        self.assertIsNone(self.Statement._get_closed_decade_for_date(date(2026, 3, 25)))

    def test_cron_does_nothing_on_non_trigger_day(self):
        before = self.Statement.search_count([])
        self.Statement._cron_generate_decade_statement(today=date(2026, 3, 15))
        after = self.Statement.search_count([])
        self.assertEqual(before, after)

    def test_cron_does_not_duplicate_existing_statement(self):
        trigger_date = date(2026, 3, 11)
        date_start, date_end, decade_number = self.Statement._get_closed_decade_for_date(trigger_date)
        self.Statement.create({
            'date_start': date_start,
            'date_end': date_end,
            'month_ref': date_start.replace(day=1),
            'decade_number': str(decade_number),
            'company_id': self.env.company.id,
        })

        before = self.Statement.search_count([])
        self.Statement._cron_generate_decade_statement(today=trigger_date)
        after = self.Statement.search_count([])

        self.assertEqual(before, after)

    def test_cron_generates_statement_on_trigger_day(self):
        trigger_date = date(2026, 3, 11)
        before = self.Statement.search_count([])
        self.Statement._cron_generate_decade_statement(today=trigger_date)
        after = self.Statement.search_count([])

        self.assertEqual(after, before + 1)
        created = self.Statement.search([], order='id desc', limit=1)
        self.assertEqual(created.date_start, date(2026, 3, 1))
        self.assertEqual(created.date_end, date(2026, 3, 10))
        self.assertEqual(created.decade_number, '1')

    # ─────────────────────────────────────────────────────────────────────
    # Protection contre la suppression
    # ─────────────────────────────────────────────────────────────────────

    def test_cannot_unlink_non_draft_statement(self):
        statement = self.Statement.create({
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 10),
            'month_ref': date(2026, 3, 1),
            'decade_number': '1',
            'company_id': self.env.company.id,
            'state': 'ready',
        })
        with self.assertRaises(UserError):
            statement.unlink()

    def test_cannot_unlink_sent_line(self):
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date=date(2026, 3, 5), amounts=[100],
        )
        invoice.action_post()

        statement = self.Statement.create({
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 10),
            'month_ref': date(2026, 3, 1),
            'decade_number': '1',
            'company_id': self.env.company.id,
        })
        statement.action_generate_lines()
        line = statement.line_ids
        line.email_sent = True

        with self.assertRaises(UserError):
            line.unlink()
