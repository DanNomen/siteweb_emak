# -*- coding: utf-8 -*-
"""Utilitaires partagés par les exports xlsx des rapports de ce module.

Plusieurs rapports construisaient leurs montants comme des chaînes déjà
formatées ("{:,.2f}".format(...)) avant de les écrire dans la feuille Excel,
ce qui produit des cellules texte : impossible de les utiliser dans une
formule (SOMME, etc.) une fois le fichier ouvert dans Excel. `to_float`
permet de récupérer la valeur numérique d'origine quelle que soit la forme
sous laquelle elle arrive (déjà un nombre, ou une chaîne formatée), pour
l'écrire comme un vrai nombre avec `AMOUNT_NUM_FORMAT` comme format
d'affichage (équivalent visuel du "{:,.2f}" d'origine, mais toujours
modifiable/utilisable dans des formules)."""

AMOUNT_NUM_FORMAT = '#,##0.00'


def to_float(value):
    """Coerce une valeur (déjà numérique, ou chaîne du type '1,234.56')
    en float. Retourne 0.0 si la valeur est vide ou non convertible."""
    if isinstance(value, (int, float)):
        return value
    if not value:
        return 0.0
    try:
        return float(str(value).replace(',', '').replace(' ', ''))
    except (TypeError, ValueError):
        return 0.0
