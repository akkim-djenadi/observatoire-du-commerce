# Veille BODACC : commerces du centre-ville

Application de l'**Observatoire du Commerce**. Pour la mettre en ligne : [DEPLOIEMENT.md](DEPLOIEMENT.md). Le logo (« Les Arcades »), ses déclinaisons, le favicon
et le guide d'usage sont dans [`assets/logo/`](assets/logo/GUIDE.md).

Mesure la vitalité commerciale du centre-ville de Montpellier, rue par rue, à partir des données publiques :
procédures collectives (BODACC), ouvertures et fermetures de commerces (Sirene), ventes de locaux (DVF).
Deux façons de l'utiliser : un tableau de bord dans le navigateur, ou des commandes en ligne.

## Les pages de l'application

| Page | Pour qui | Contenu |
|---|---|---|
| Commerces en difficulté | Observatoire | Procédures collectives, carte, fiche de chaque commerce et **fiche d'aide** pour les commerces encore sauvables |
| Chiffres clés | Public, presse | Les 5 grands chiffres, l'indice mois par mois, le classement des rues, la note PDF, le code pour **intégrer un graphique** dans un article |
| Vitalité des rues | Observatoire, élus | Indice de vitalité sur 100 par zone et par rue, ses six composantes, l'offre de chaque rue, ouvertures et fermetures |
| S'installer | Porteurs de projet | Carte des locaux confirmés ou probablement libérés, repères par rue (indice, ce qui manque, prix des locaux) |
| Comparer les villes | Tous | Défaillances, créations et dynamisme de plusieurs villes, avec une vue « Comprendre les chiffres » |

## Ce qui tourne tout seul (GitHub Actions)

- **Collecte mensuelle** (`.github/workflows/collecte.yml`), le 2 de chaque mois :
  `collecte.py` récupère les commerces (Sirene), les ventes de locaux (DVF) et les procédures (BODACC),
  calcule l'indice et l'ajoute à `data/indice_historique.csv`, puis `note.py` produit la note PDF dans
  `rapports/`. Le tout est commité : l'application en ligne se met à jour toute seule.
- **Alerte hebdomadaire** (`.github/workflows/alerte.yml`), chaque lundi : `alerte.py` cherche les commerces
  du centre-ville placés en redressement ou en sauvegarde dans la semaine et ouvre un **ticket GitHub**,
  que GitHub vous envoie par e-mail.

Les mêmes commandes se lancent à la main :

```bash
python3 collecte.py
```

```bash
python3 note.py
```

```bash
python3 alerte.py --depuis 2026-11-01 --sec
```

## Tableau de bord (navigateur)

Double-cliquer sur `Lancer_veille.command`, ou dans un terminal, depuis ce dossier :

```bash
python3 -m streamlit run app.py
```

Le tableau de bord s'ouvre à l'adresse http://localhost:8501. Dans le panneau de gauche, choisir la
ville, la période (les X derniers mois, ou de tel mois à tel mois) et les types d'annonce, puis
**Lancer la recherche**. Ensuite :

- **Filtres** au-dessus des chiffres : zones, secteurs, statuts, recherche par nom, rue ou SIREN.
- **Carte** : chaque commerce coloré selon son statut (ocre = encore sauvable, terracotta =
  liquidation, gris = clôturé).
- **Tendances** : répartition par zone et par secteur, courbe d'évolution mois par mois (ouvertures,
  conversions en liquidation, clôtures), annonces publiées chaque mois par type.
- **Commerces** : cliquer sur une ligne pour voir l'historique et le texte de chaque jugement.
- **Annonces** : toutes les annonces, avec le lien vers bodacc.fr.
- **Télécharger l'Excel** : le fichier reprend exactement la vue filtrée.

Une recherche déjà faite reste en mémoire 6 heures et s'affiche alors immédiatement.

### Page « Comparer les villes »

Compare jusqu'à 7 villes françaises sur plusieurs années (depuis 2017), mois par mois :

- **Indicateurs** : défaillances (jugements d'ouverture de redressement, sauvegarde ou liquidation),
  créations d'entreprises, radiations, et **dynamisme** = créations pour 1 défaillance.
- **Pour 10 000 habitants** (population INSEE) : rend comparables des villes de tailles différentes.
- **Périmètre** : toutes activités, ou commerces seulement (estimation par mots-clés, vente en ligne exclue).
- **Lissage** sur 3 ou 12 mois pour lire la tendance plutôt que les à-coups.
- Classements, tableau récapitulatif (avec l'évolution sur 12 mois) et export CSV des séries.

Toute ville peut être ajoutée en tapant son nom. Montpellier garde toujours la couleur terracotta et
chaque ville garde sa couleur quand on en ajoute ou retire d'autres. Le mois en cours, incomplet,
est exclu.

## Lancer une recherche en ligne de commande

Dans un terminal, depuis ce dossier :

```bash
python3 main.py
```

Le programme couvre les 6 derniers mois et enregistre le fichier dans le dossier `exports/`.

### Choisir la période

Les 3 derniers mois :

```bash
python3 main.py --mois 3
```

De mars 2025 à juin 2026 inclus (un mois seul est pris en entier) :

```bash
python3 main.py --debut 03/2025 --fin 06/2026
```

Toute l'année 2025 :

```bash
python3 main.py --debut 2025 --fin 2025
```

Formats de date acceptés : `2025`, `03/2025`, `2025-03`, `15/03/2025`, `2025-03-15`.

### Filtrer par type d'annonce

| Mot-clé | Annonces gardées |
|---|---|
| `redressement` | ouverture de redressement judiciaire |
| `liquidation` | liquidation judiciaire (ouverture ou conversion) |
| `sauvegarde` | procédure de sauvegarde |
| `plan` | plan de redressement ou de cession |
| `cloture` | clôture de la procédure |
| `creances` | état ou liste des créances |
| `faillite` | faillite personnelle |
| `autre` | autres jugements et ordonnances |

Séparer plusieurs mots-clés par des virgules :

```bash
python3 main.py --annonces redressement,sauvegarde
```

Le filtre ne garde que les commerces ayant au moins une annonce de ce type. Leur statut et leur
historique tiennent compte de toutes leurs annonces : on voit par exemple qu'un redressement
s'est ensuite transformé en liquidation.

### Combiner les options

```bash
python3 main.py --debut 2025 --fin 2025 --annonces liquidation --sortie ~/Desktop/liquidations_2025.xlsx
```

Pour voir toutes les options :

```bash
python3 main.py --help
```

Une recherche prend 1 à 2 minutes. Les suivantes vont plus vite : les fiches entreprises déjà
consultées sont gardées dans `cache/`.

## Prérequis

Python 3.10 ou plus. `requirements.txt` liste ce dont l'application a besoin pour tourner ; `requirements-dev.txt`
y ajoute les outils de test et de vectorisation du logo. En local :

```bash
pip3 install -r requirements-dev.txt
```

Aucune clé ni abonnement : toutes les sources sont publiques et gratuites.

## Modifier les règles

Tout se règle dans `config.py` : contour de l'Écusson, distances de l'hypercentre (750 m) et des
faubourgs (1 300 m), activités considérées comme des commerces, adresses de domiciliation à écarter.

## Vérifier le programme

```bash
python3 -m pytest tests
```
