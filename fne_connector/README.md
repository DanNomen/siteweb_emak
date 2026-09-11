# FNE Connector — Odoo 18 Community

Connecte la facturation Odoo à la plateforme **Facture Normalisée Électronique**
de la Direction Générale des Impôts de Côte d'Ivoire.

Conforme à la *Procédure d'interfaçage des entreprises par API* (DGI, mai 2025).

---

## 1. Installation

```bash
# Copier le module dans un répertoire d'addons
cp -r fne_connector /path/to/odoo/addons/

# Redémarrer Odoo puis, dans Applications, activer le mode développeur,
# « Mettre à jour la liste des applications », rechercher « FNE ».
```

Dépendance Python : `requests` (déjà présent dans une installation Odoo standard).

> Odoo Online (SaaS) n'accepte pas les modules tiers. Ce module nécessite
> **Odoo.sh** ou une installation **on-premise**.

## 2. Ordre de mise en route

L'obtention de la clé API dépend d'une validation par la DGI qui prend
plusieurs semaines. Commencez par là, pas par le développement.

1. Inscrire l'entreprise sur l'environnement de test : `http://54.247.95.108`
2. Paramétrer dans l'espace FNE les **points de vente** et **établissements**
3. Installer et configurer ce module en environnement de test
4. Émettre des factures de test : vente B2B, vente B2C, avoir partiel, et si
   applicable bordereau d'achat agricole
5. Transmettre les spécimens à **support.fne@dgi.gouv.ci**
6. Après validation : basculer sur l'URL de production fournie par la DGI et
   récupérer la clé API définitive dans l'onglet « Paramétrage » de l'espace FNE

## 3. Configuration dans Odoo

### Comptabilité → Configuration → Paramètres → bloc « FNE »

| Champ | Remarque |
|---|---|
| Environnement | Test / Production |
| URL de la plateforme | `http://54.247.95.108/ws` en test |
| Clé API | Visible par le gestionnaire principal uniquement, après validation DGI |
| NCC de l'entreprise | Ex. `9606123E` |
| Point de vente / Établissement | **Valeurs exactes** déclarées dans l'espace FNE, sinon HTTP 400 |
| Certifier à la validation | Envoi automatique au `action_post` |
| Bloquer en cas d'échec | Annule la validation si la FNE refuse la facture |

### Comptabilité → Configuration → Taxes → onglet « FNE »

Chaque taxe utilisée sur des factures clients doit être mappée :

| Taxe Odoo | Nature FNE | Code |
|---|---|---|
| TVA 18 % | TVA | `TVA` |
| TVA 9 % | TVA | `TVAB` |
| Exonération conventionnelle | TVA | `TVAC` |
| Exonération légale (TEE, RME) | TVA | `TVAD` |
| AIRSI, GRA, DTD… | Autre taxe | nom exact attendu par la FNE |

**Les taxes incluses dans le prix ne sont pas supportées** : la FNE attend un
prix unitaire hors taxes. Le module lève une erreur explicite si une taxe
`price_include` est rencontrée.

### Contacts

`fne_ncc` (NCC du client) et `fne_template` sur la fiche partenaire.
Si le template est laissé vide, il est déduit ainsi :

- pays ≠ Côte d'Ivoire → **B2F** (`foreignCurrency` et `foreignCurrencyRate`
  deviennent obligatoires)
- NCC renseigné → **B2B**
- sinon → **B2C**

**B2G** (institution gouvernementale) doit toujours être choisi manuellement :
rien dans les données Odoo ne permet de le déduire de façon fiable.

## 4. Fonctionnement

### Facture de vente

`POST $url/external/invoices/sign` déclenché à la validation. La réponse
alimente :

- `fne_reference` → **numéro légal**, c'est lui qui fait foi fiscalement
- `fne_token` → converti en QR code et imprimé sur le PDF
- `fne_invoice_id` et `fne_item_id` sur chaque ligne → requis pour les avoirs
- `balance_sticker` → solde de stickers, avec alerte sous le seuil configuré

### Avoir

`POST $url/external/invoices/{id}/refund`. L'avoir **doit** être créé depuis la
facture d'origine (bouton « Ajouter un avoir »), car la FNE identifie les lignes
par leur identifiant technique. Ne modifiez ni les articles ni les prix unitaires
dans un avoir : le rapprochement échouerait.

### Bordereau d'achat de produits agricoles

Même endpoint, avec `fne_invoice_type = purchase` sur la facture.

## 5. Gestion des erreurs

| Statut FNE | Signification | Action |
|---|---|---|
| À envoyer | En attente d'envoi | Bouton « Certifier » ou tâche planifiée |
| Certifiée | Numéro légal obtenu | — |
| Erreur | Refus explicite de la FNE (400/401) | Corriger puis « Renvoyer à la FNE » |
| À vérifier | **Aucune réponse reçue** | Vérifier dans l'espace FNE avant tout renvoi |

Le statut *À vérifier* couvre le cas d'une coupure réseau après l'envoi : la
facture a peut-être été certifiée côté DGI. Le module ne rejoue **jamais**
automatiquement ces cas, pour éviter une double certification. Après
vérification humaine, le bouton « Saisir le résultat FNE » permet de reporter le
numéro légal constaté dans l'espace FNE.

Une facture certifiée ne peut plus être repassée en brouillon ni supprimée.

Tous les échanges (requête et réponse brutes) sont tracés dans
**Comptabilité → Écritures comptables → Échanges FNE**, y compris lorsque la
transaction est annulée.

## 6. Tâche planifiée

*Paramètres techniques → Actions planifiées → « FNE : reprise des factures non
certifiées »*, **désactivée par défaut**. Activez-la si vous décochez
« Certifier à la validation », ou pour rattraper automatiquement les erreurs
métier. Elle ignore volontairement les factures « À vérifier ».

## 7. Points à valider en environnement de test

Ces éléments ne sont pas totalement explicites dans le document DGI et méritent
une confirmation par vos spécimens :

- **`foreignCurrencyRate`** : le module transmet le taux de conversion de la
  devise de la facture vers la devise de la société. Vérifiez le sens attendu
  par la plateforme.
- **`discount`** : transmis en pourcentage, comme dans Odoo. Un `discount`
  global au niveau de l'entête n'est pas géré (Odoo n'a pas de champ natif
  correspondant).
- **Totaux** : la FNE recalcule les montants à partir des lignes. Comparez
  systématiquement `vatAmount` renvoyé avec le total de taxes Odoo — un écart
  signale une divergence d'arrondi ou de mapping de taxes.
- **`measurementUnit`** : le nom de l'UdM Odoo est transmis tel quel. Vérifiez
  que la FNE accepte vos libellés.

## 8. Points d'extension

- `fne.api` est un `AbstractModel` : surchargez `_request` pour brancher un mock
  en tests automatisés.
- `_fne_prepare_payload` et `_fne_prepare_line` sont conçus pour être surchargés
  si vos règles métier diffèrent.
