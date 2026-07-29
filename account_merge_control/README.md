# Account Merge Control — Guide d'utilisation

Module Odoo 18 — `account_merge_control`
**Version :** 18.0.1.0.0 | **Société :** EMAK / APPROMED

---

## Sommaire

1. [Objectif](#1-objectif)
2. [Comment fonctionne la fusion dans Odoo](#2-comment-fonctionne-la-fusion-de-comptes-dans-odoo)
3. [Ce que ce module ajoute](#3-ce-que-ce-module-ajoute)
4. [Utilisation pas à pas](#4-utilisation-pas-à-pas)
5. [Comprendre ce qui se passe après la fusion](#5-comprendre-ce-qui-se-passe-après-la-fusion)
6. [Fusions prévues EMAK / APPROMED](#6-fusions-prévues-emak--appromed)
7. [Journal d'audit](#7-journal-daudit)
8. [FAQ et Erreurs fréquentes](#8-faq--erreurs-fréquentes)

---

## 1. Objectif

Ce module ajoute une **surcouche de sécurité** au wizard natif de fusion de comptes d'Odoo (`account.merge.wizard`). Il permet de :

- Simuler la fusion **sans modifier la base** (mode dry-run)
- Vérifier l'impact **avant** d'agir (nombre de pièces, solde concerné)
- Bloquer automatiquement si des **périodes comptables verrouillées** sont concernées
- Exécuter la fusion dans un **savepoint** (annulation automatique en cas d'erreur)
- Conserver un **journal d'audit complet** (qui, quand, quoi, combien de pièces, soldes)

---

## 2. Comment fonctionne la fusion de comptes dans Odoo

> **Important à comprendre avant d'utiliser le wizard.**

### Le wizard natif

Le wizard de fusion est lancé depuis :
**Comptabilité → Plan comptable → (sélectionner 2+ comptes en liste) → Action → Fusionner les comptes**

### Regroupement automatique

Odoo regroupe les comptes sélectionnés par **type de compte** (Fournisseur réconciliable, Client non-commercial, etc.).
Chaque groupe correspond à une fusion potentielle.

### La règle cruciale : QUI devient la destination ?

> **Le 1er compte de chaque groupe (ligne du HAUT) est la DESTINATION** — il reste et reçoit tout.
> **Les comptes suivants sont les SOURCES** — ils sont vidés puis supprimés.

```
Groupe : Commerce Fournisseur (Réconciliable)

  ☑ 41110000 Fournisseurs  ← DESTINATION (reste, reçoit les pièces)
  ☑ 411100   Fournisseurs  ← SOURCE (vidé, puis supprimé définitivement)
```

> Si vous voulez fusionner VERS 41110000, assurez-vous que 41110000 est EN PREMIER dans la liste.

### Ce qui se passe techniquement lors de la fusion

1. Toutes les **pièces comptables** (lignes account.move.line) du compte source → réaffectées au compte destination
2. Toutes les **références** (budgets, règles de rapprochement…) → mises à jour
3. Le **compte source est supprimé** définitivement de la base de données
4. Les **traductions** du nom du compte sont fusionnées
5. Le cache du registre Odoo est vidé

---

## 3. Ce que ce module ajoute

### Section "Contrôle et sécurité" dans le wizard

| Champ | Description |
|-------|-------------|
| **Mode simulation (dry-run)** | Coché par défaut. Simule sans rien modifier. |
| **Forcer si période verrouillée** | Outrepasse le blocage sur dates verrouillées (dangereux). |
| **Tapez CONFIRMER** | Apparaît si > 100 pièces. Sécurité anti-clic accidentel. |
| **Nb pièces à transférer** | Calculé par le bouton "Aperçu (dry-run)". |
| **Solde total concerné** | Solde cumulé des pièces à déplacer. |

### Bouton "Aperçu (dry-run)"

Calcule et affiche le nombre de pièces et le solde concernés **sans aucune modification** de la base.
Utilisez-le toujours avant d'exécuter la fusion réelle.

### Autorisation des fusions intra-société

Le wizard natif Odoo bloque la fusion de deux comptes de la **même société**.
Ce module **supprime cette restriction**, car le besoin EMAK/APPROMED est précisément
de fusionner des comptes au sein de la même société (ex : 411100 → 41110000 chez APPROMED MALI).

---

## 4. Utilisation pas à pas

### Étape 1 — Sélectionner les comptes

1. Aller dans **Comptabilité → Comptabilité → Plan comptable**
2. Passer en **vue liste**
3. **Cocher** les comptes à fusionner (ex : 411100 et 41110000)
4. Cliquer sur **Action → Fusionner les comptes**

### Étape 2 — Vérifier l'ordre dans le wizard

Le wizard s'ouvre. Vérifier que **le compte destination** (celui qui doit rester) est **en haut du groupe**.

> Si l'ordre est inversé : fermez le wizard, revenez à la liste,
> et re-sélectionnez les comptes en cochant **d'abord le compte destination**.

### Étape 3 — Utiliser le dry-run (obligatoire)

1. "Mode simulation (dry-run)" doit être **coché** (défaut)
2. Cliquer sur **"Aperçu (dry-run)"**
3. Une notification affiche : `X pièces comptables seront transférées depuis Y compte(s) source`
4. Vérifier les champs **"Nb pièces à transférer"** et **"Solde total concerné"**
5. L'opération est enregistrée dans le **journal d'audit** avec statut `Simulation`

### Étape 4 — Exécuter la fusion réelle

Seulement si le dry-run vous satisfait :

1. **Décocher** "Mode simulation (dry-run)"
2. Si > 100 pièces : le champ "Tapez CONFIRMER" apparaît → saisir exactement `CONFIRMER`
3. Cliquer sur **"Fusionner"**
4. La notification `Comptes fusionnés avec succès !` s'affiche

### Étape 5 — Vérifier le résultat

> **La fusion ne rafraîchit pas automatiquement l'écran.**

Après la notification de succès :

1. **Fermer** le wizard (bouton Annuler ou croix)
2. **Rafraîchir la page** (touche F5 ou naviguer ailleurs puis revenir)
3. Aller dans **Plan comptable** et vérifier que :
   - Le **compte source** (2ème de la liste) a **disparu**
   - Le **compte destination** (1er de la liste) est toujours là
   - Le solde du compte destination inclut maintenant les pièces transférées

---

## 5. Comprendre ce qui se passe après la fusion

### Ce que vous devez observer

```
AVANT la fusion :
  41110000  Fournisseurs  |  50 pièces  |  solde  5 000 CFA  (destination)
  411100    Fournisseurs  |  30 pièces  |  solde  3 000 CFA  (source)

APRÈS la fusion :
  41110000  Fournisseurs  |  80 pièces  |  solde  8 000 CFA  ← tout ici
  411100                  |  SUPPRIMÉ   |
```

### Le compte source est supprimé définitivement

Le compte source n'apparaît **plus du tout** dans le plan comptable.
C'est **irréversible** (sauf restauration de sauvegarde).

### Les pièces ne changent pas de montant

La fusion déplace les pièces d'un compte à l'autre, elle ne les modifie pas.
Les montants, dates et journaux restent identiques. Seul le **compte impacté** (account_id) change.

### Pourquoi pas de changement visible immédiatement ?

Odoo affiche le wizard dans une fenêtre modale. Après la fusion :
- La notification de succès s'affiche → la fenêtre se ferme
- **Mais la vue derrière n'est PAS rechargée automatiquement**

**Solution :** Appuyez sur **F5** ou naviguez vers un autre menu puis revenez.

---

## 6. Fusions prévues EMAK / APPROMED

Ordre recommandé d'exécution (toujours dry-run d'abord) :

| # | Société | Source (à supprimer) | Destination (à conserver) | Pièces estimées | Remarque |
|---|---------|---------------------|--------------------------|----------------|----------|
| 1 | APPROMED | 41100000 | 41110000 | ~6 | Faible volume — commencer par celui-là |
| 2 | EMAK MED | 411100 | 41110000 | ~735 | Volume moyen |
| 3 | APPROMED | 411100 | 41110000 | ~7920 | **Gros volume — faire en DERNIER** |

> Faire les fusions dans l'ordre indiqué. Le plus gros volume en dernier pour limiter le risque.

### Comment sélectionner les comptes dans le bon ordre

Pour que 41110000 soit la **destination** (premier dans le wizard) :

1. Dans le plan comptable, cocher **d'abord** 41110000
2. Puis cocher 411100 (ou 41100000)
3. Lancer Action → Fusionner les comptes
4. Vérifier dans le wizard que 41110000 est bien en haut du groupe

### Après les 3 fusions

Aller dans le Plan comptable et s'assurer que `41100000` et `411100` **n'existent plus**.
S'ils persistent encore (cas rare), les **archiver** (Actif = Non) pour empêcher toute réutilisation.

---

## 7. Journal d'audit

Chaque opération (simulation ou réelle) est enregistrée dans :
**Comptabilité → Configuration → Journal des fusions**

| Colonne | Description |
|---------|-------------|
| Date | Horodatage de l'opération |
| Compte(s) source | Comptes qui ont été vidés/supprimés |
| Compte destination | Compte qui a reçu les pièces |
| Nb pièces | Nombre de lignes comptables transférées |
| Solde source avant | Solde cumulé avant fusion |
| Statut | `Simulation` / `Fusion exécutée` / `Échec/Rollback` |
| Exécuté par | Utilisateur qui a lancé l'opération |

En cas d'**échec**, la fusion est annulée automatiquement (rollback savepoint)
et le message d'erreur technique est stocké dans le journal.

---

## 8. FAQ & Erreurs fréquentes

### "Sélectionnez au moins 2 comptes dans un même groupe"

Vous n'avez sélectionné qu'un seul compte, ou les comptes sont de types différents
(ils ne se retrouvent pas dans le même groupe). Retournez au plan comptable et
sélectionnez au moins 2 comptes **du même type**.

### "Des écritures antérieures à la date de verrouillage…"

Des pièces sur le compte source sont datées avant la date de verrouillage fiscal.
La fusion est bloquée pour protéger l'intégrité comptable.
Cochez **"Forcer même si période verrouillée"** uniquement si vous êtes certain.

### "X pièces vont être transférées. Tapez CONFIRMER…"

Sécurité anti-clic accidentel pour les fusions volumineuses (> 100 pièces).
Saisissez exactement `CONFIRMER` (majuscules, sans espace) dans le champ prévu.

### "La fusion a réussi mais je ne vois pas de changement"

C'est normal — le compte source a bien été supprimé. **Rafraîchissez la page (F5)**.
Le compte source doit avoir disparu du plan comptable.

### La fusion s'est exécutée dans le mauvais sens

**Le 1er compte = destination (reste), le 2ème = source (supprimé).**
Si c'est inversé et que des données sont perdues, il faut restaurer la sauvegarde.
C'est pour cela que le dry-run est **obligatoire par défaut**.

---

## Dépendances

- Module natif Odoo 18 : `account`
- Aucun autre module custom requis

## Support

En cas d'anomalie, consulter **Comptabilité → Configuration → Journal des fusions**
pour le message d'erreur technique complet.
