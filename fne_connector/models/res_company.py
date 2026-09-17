from odoo import fields, models

FNE_TEST_URL = "http://54.247.95.108/ws"


class ResCompany(models.Model):
    _inherit = "res.company"

    fne_enabled = fields.Boolean(
        string="Activer la FNE",
        help="Active la certification des factures auprès de la plateforme FNE de la DGI.",
    )
    fne_environment = fields.Selection(
        [("test", "Test"), ("prod", "Production")],
        string="Environnement FNE",
        default="test",
        required=True,
    )
    fne_base_url = fields.Char(
        string="URL de la plateforme",
        default=FNE_TEST_URL,
        help="Environnement de test : %s\n"
             "Production : URL transmise par la DGI après validation de l'interfaçage."
             % FNE_TEST_URL,
    )
    fne_api_key = fields.Char(
        string="Clé API",
        groups="base.group_system",
        help="Onglet « Paramétrage » de votre espace FNE. Visible uniquement par le "
             "gestionnaire principal, après validation par la DGI.",
    )
    fne_ncc = fields.Char(
        string="NCC de l'entreprise",
        help="Numéro de Compte Contribuable de l'émetteur.",
    )
    fne_point_of_sale = fields.Char(
        string="Point de vente par défaut",
        help="Doit correspondre EXACTEMENT à un point de vente déclaré dans votre "
             "espace FNE, sinon la plateforme renvoie une erreur 400.",
    )
    fne_establishment = fields.Char(
        string="Établissement par défaut",
        help="Doit correspondre EXACTEMENT à un établissement déclaré dans votre espace FNE.",
    )
    fne_commercial_message = fields.Char(string="Message commercial")
    fne_payment_instruction = fields.Text(
        string="Instructions de paiement",
        help="Mention libre imprimée sur la facture, avant le tableau des lignes "
             "(ex. « PAIEMENT PAR ORANGE MONEY  #144*491# / 0716828155 »). "
             "Les retours à la ligne sont conservés à l'impression. "
             "Laisser vide pour ne rien imprimer.",
    )
    fne_footer = fields.Char(
        string="Mention légale de pied de page",
        help="Mention légale imprimée dans le pied de page du PDF, donc en bas de "
             "CHAQUE page (ex. capital social, adresse, RCCM). Vient s'ajouter "
             "sous le pied de page standard de la société.",
    )
    fne_certify_on_post = fields.Boolean(
        string="Certifier à la validation",
        default=True,
        help="Envoie la facture à la FNE automatiquement lors de sa validation. "
             "Sinon, la certification se fait manuellement ou via la tâche planifiée.",
    )
    fne_block_on_error = fields.Boolean(
        string="Bloquer en cas d'échec",
        default=False,
        help="Si coché, un refus de la FNE annule la validation de la facture. "
             "Sinon la facture est validée avec le statut FNE « Erreur » et devra "
             "être renvoyée. Une erreur réseau ne bloque jamais la validation.",
    )
    fne_timeout = fields.Integer(
        string="Timeout (s)",
        default=30,
        help="Délai d'attente maximum d'une réponse de la plateforme FNE.",
    )
    fne_sticker_threshold = fields.Integer(
        string="Seuil d'alerte stickers",
        default=50,
        help="Une alerte est journalisée lorsque le solde de stickers renvoyé par "
             "la FNE passe sous ce seuil.",
    )
