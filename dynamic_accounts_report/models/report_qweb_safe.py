# -*- coding: utf-8 -*-
"""Rendu QWeb tolérant aux données manquantes pour les PDF de ce module.

Tous les templates PDF de ce module lisent leurs valeurs par accès direct
(``grand_total['diff0_sum_display']``, ``total[partner]['debit_sum']``,
``filters['end_date']``...) dans un dictionnaire construit **côté client**
et envoyé tel quel dans l'action ``ir.actions.report``.

Or ``JSON.stringify`` supprime purement et simplement les clés dont la
valeur vaut ``undefined`` : il suffit que l'utilisateur clique sur PDF
avant la fin du chargement des données (ou après un chargement en erreur)
pour que ces clés n'arrivent jamais au serveur. QWeb lève alors un
``KeyError`` transformé en ``RPC_ERROR`` côté navigateur, par exemple :

    KeyError: 'diff0_sum_display'
    Template: dynamic_accounts_report.aged_receivable
    Node: <t t-out="grand_total['diff0_sum_display']"/>

Plutôt que de rendre défensif chaque accès des dix templates (et de devoir
le refaire à chaque nouvelle clé), on enveloppe une fois pour toutes le
contexte de rendu des rapports du module dans des structures tolérantes :

* une clé absente renvoie :data:`MISSING`, qui s'affiche comme une chaîne
  vide, est faux dans un ``t-if``, vide dans un ``t-foreach`` et vaut 0.0
  dans un calcul (``float(grand_total['total_debit'])``,
  ``total[x]['total_debit'] - total[x]['total_credit']``...) ;
* une clé ``<x>_display`` absente est reconstituée à partir de ``<x>``
  s'il est présent, avec le même formatage que le client
  (``formatNumberWithSeparators`` : entier, espace comme séparateur de
  milliers) : le PDF affiche le bon montant au lieu d'une case vide.
"""
from odoo import models

#: Préfixe des rapports concernés (report_name / xml_id de l'action).
MODULE_PREFIX = 'dynamic_accounts_report.'

#: Clés du contexte de rendu laissées telles quelles (recordsets Odoo et
#: métadonnées du moteur de rapport).
_UNWRAPPED_KEYS = frozenset({
    'docs', 'doc_ids', 'doc_model', 'report_type', 'is_html_empty',
})

_DISPLAY_SUFFIX = '_display'


class _Missing(float):
    """Valeur de repli pour une clé absente.

    Sous-classe de ``float`` (valeur 0.0) pour rester utilisable dans les
    quelques templates qui calculent avec ces valeurs, mais qui s'affiche
    comme une chaîne vide et se comporte comme une collection vide.
    """
    __slots__ = ()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls, 0.0)
        return cls._instance

    def __str__(self):
        return ''

    def __repr__(self):
        return ''

    def __format__(self, format_spec):
        return float.__format__(self, format_spec) if format_spec else ''

    def __bool__(self):
        return False

    # Se comporte comme un dict/une liste vide : `x['a']['b']` ne casse pas
    # la chaîne d'accès et `t-foreach` ne produit aucune ligne.
    def __getitem__(self, key):
        return self

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __contains__(self, key):
        return False

    def get(self, key, default=None):
        return default

    def keys(self):
        return []

    def values(self):
        return []

    def items(self):
        return []


#: Singleton renvoyé pour toute clé absente.
MISSING = _Missing()


def format_display(value):
    """Formate un montant comme le fait le client JS.

    ``formatNumberWithSeparators`` arrondit à l'entier et utilise l'espace
    comme séparateur de milliers ("1 234 567"). Toute valeur non numérique
    est renvoyée telle quelle.
    """
    if isinstance(value, str):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return MISSING
    return '{:,.0f}'.format(number).replace(',', ' ')


def safe_value(value):
    """Rend `value` tolérant aux clés absentes, récursivement (à la volée)."""
    if value is None:
        return MISSING
    if isinstance(value, (SafeDict, SafeList, _Missing)):
        return value
    if isinstance(value, dict):
        return SafeDict(value)
    if isinstance(value, list):
        return SafeList(value)
    return value


class SafeDict(dict):
    """Dict dont une clé absente vaut :data:`MISSING` au lieu de lever."""
    __slots__ = ()

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return safe_value(dict.__getitem__(self, key))
        return self.__missing__(key)

    def __missing__(self, key):
        # 'debit_sum_display' absent mais 'debit_sum' présent : le client
        # n'a pas envoyé la chaîne pré-formatée, on la reconstruit.
        if isinstance(key, str) and key.endswith(_DISPLAY_SUFFIX):
            base = key[:-len(_DISPLAY_SUFFIX)]
            if dict.__contains__(self, base):
                return format_display(dict.__getitem__(self, base))
        return MISSING

    def get(self, key, default=None):
        # Sémantique standard conservée (un défaut explicite l'emporte),
        # seules les valeurs renvoyées sont rendues tolérantes.
        if dict.__contains__(self, key):
            return safe_value(dict.__getitem__(self, key))
        return default

    def values(self):
        return [safe_value(value) for value in dict.values(self)]

    def items(self):
        return [(key, safe_value(value)) for key, value in dict.items(self)]


class SafeList(list):
    """Liste dont les éléments sont rendus tolérants à la volée."""
    __slots__ = ()

    def __getitem__(self, index):
        return safe_value(list.__getitem__(self, index))

    def __iter__(self):
        return (safe_value(value) for value in list.__iter__(self))


def safe_rendering_context(values):
    """Applique :func:`safe_value` à tout le contexte de rendu d'un rapport."""
    return {
        key: value if key in _UNWRAPPED_KEYS else safe_value(value)
        for key, value in values.items()
    }


class IrActionsReport(models.Model):
    """Applique le contexte de rendu tolérant aux rapports de ce module."""
    _inherit = 'ir.actions.report'

    def _dynamic_accounts_report_name(self, args, kwargs):
        """Nom du rapport en cours de rendu, quelle que soit la signature.

        Selon la version d'Odoo, `_get_rendering_context` reçoit soit
        l'enregistrement `ir.actions.report`, soit sa référence (xml_id),
        soit rien du tout (le rapport est alors `self`). Les trois formes
        commencent par le nom du module pour les rapports concernés.
        """
        report = kwargs.get('report', args[0] if args else None)
        if isinstance(report, str):
            return report
        name = getattr(report, 'report_name', None)
        if not name and len(self) == 1:
            name = self.report_name
        return name or ''

    def _get_rendering_context(self, *args, **kwargs):
        values = super()._get_rendering_context(*args, **kwargs)
        if not isinstance(values, dict):
            return values
        if not self._dynamic_accounts_report_name(args, kwargs).startswith(
                MODULE_PREFIX):
            return values
        return safe_rendering_context(values)
