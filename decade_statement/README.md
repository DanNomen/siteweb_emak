# Relevé par Décade

Ce module génère et permet l'envoi de relevés de factures clients (Brouillon + Validées) regroupés par tranches de 10 jours (décades).

## 1. Fonctionnement Automatique (Cron)

Le module contient une action planifiée (Cron) qui s'exécute automatiquement tous les **10 jours**.
- Le système découpe chaque mois en 3 décades :
  - **Décade 1 :** du 1er au 10 du mois
  - **Décade 2 :** du 11 au 20 du mois
  - **Décade 3 :** du 21 à la fin du mois (28, 29, 30 ou 31)
- Lors de l'exécution, un nouveau relevé est créé. Toutes les factures clients de la période sont analysées, regroupées par client (Partenaire) et stockées dans le relevé.

## 2. Utilisation Manuelle

Si vous souhaitez générer un relevé en dehors du cycle automatique, ou pour une période personnalisée :

1. Allez dans le menu : **Facturation > Clients > Relevés par Décade** (ou depuis le menu de Facturation si un raccourci direct y est placé).
2. Cliquez sur **Nouveau** pour créer un lot de relevés.
3. Renseignez la **Date de début** et la **Date de fin** de la période souhaitée.
4. Cliquez sur le bouton **Générer les lignes clients**. 
   - *Odoo va automatiquement chercher toutes les factures (brouillons et validées) comprises entre ces deux dates et générer une ligne récapitulative pour chaque client.*
5. Une fois les lignes générées, l'état du relevé passe à **Généré**.

## 3. Envoi des Relevés par Email

L'envoi des relevés aux clients se fait de manière **manuelle** pour vous permettre de contrôler ce qui part.

1. Ouvrez un Relevé par Décade qui a le statut **Généré**.
2. Allez dans l'onglet **Lignes par Client**. Vous verrez la liste des clients ayant des factures sur la période.
3. Pour envoyer le relevé à un client spécifique, cliquez sur le bouton **Envoyer Email (✉)** situé au bout de la ligne du client concerné.
4. L'email est envoyé en utilisant le modèle configuré, qui contient un tableau récapitulatif détaillé des factures (N°, Date, État, Montant) et le total dû. Le client recevra ce récapitulatif directement dans le corps de l'email.

## 4. Consultation des Détails

- Depuis un Relevé par Décade, vous pouvez à tout moment cliquer sur une ligne client pour voir le détail des factures qui composent son relevé (onglet "Factures" sur le formulaire de la ligne).
- Tant que l'email n'a pas été envoyé pour ce client, vous pouvez retirer/ajouter des factures directement sur cette ligne (ex : exclure une facture contestée). Une fois l'email envoyé, la liste est figée pour garder une trace fidèle de ce qui a été transmis.
- Vous pouvez visualiser instantanément le **Montant Total** dû par chaque client pour la période sélectionnée (converti dans la devise de la société si les factures sont dans une autre devise).

## 5. Multi-société

Le cron parcourt toutes les sociétés actives et génère un relevé distinct par société pour la période courante.

## 6. Archivage et suppression

- Un relevé ne peut être supprimé que s'il est encore en **Brouillon** ; au-delà, archivez-le (bouton Actions > Archiver) plutôt que de le supprimer, pour conserver l'historique.
- Une ligne client dont l'email a déjà été envoyé ne peut pas être supprimée.
