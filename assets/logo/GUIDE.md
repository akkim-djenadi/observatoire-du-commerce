# Observatoire du Commerce : guide d'usage du logo

## 1. Le logo
- **Idée** : un « m » dessiné comme deux arcades marchandes. Il évoque Montpellier et ses rez-de-chaussée commerçants.
- **Versions**
  - horizontale `final/observatoire-horizontal.svg` (version principale)
  - empilée `final/observatoire-empile.svg`
  - symbole seul `final/observatoire-symbole.svg`
  - version renforcée pour les petites tailles `final/observatoire-symbole-petit.svg`
- **Fichiers prêts à l'emploi** dans `final/web/`
  - noir, blanc, terracotta et terracotta foncé
  - carré pour avatar
  - icône d'application
  - `favicon.ico`, `favicon.svg`, icônes PNG de 16 à 512 px, `site.webmanifest` et `head-snippet.html` à coller dans le `<head>` d'un site
- **Construction** : un seul module. Les piliers (28 unités sur 256) et la traverse (26 unités) ont presque la même
  épaisseur. La traverse est volontairement un peu plus fine, car une horizontale paraît plus épaisse qu'une verticale.

## 2. Zone de protection
Laisser autour du logo une marge libre au moins égale à **la largeur d'un pilier** du symbole. Elle grandit avec le logo.

## 3. Tailles minimales
| Version | Écran | Impression |
|---|---|---|
| Horizontale | 160 px de large | 35 mm de large |
| Symbole | 24 px | 8 mm |
| Symbole petit (`observatoire-symbole-petit.svg`, favicon) | 16 px | 6 mm |

## 4. Couleurs
| Nom | HEX | RVB | CMJN (conversion indicative) |
|---|---|---|---|
| Terracotta (couleur du logo) | `#BB502E` | 187 / 80 / 46 | 0 / 57 / 75 / 27 |
| Terracotta foncé | `#8A3A20` | 138 / 58 / 32 | 0 / 58 / 77 / 46 |
| Ocre (accent) | `#E2A24A` | 226 / 162 / 74 | 0 / 28 / 67 / 11 |
| Sable (fonds clairs, logo inversé) | `#F6ECE4` | 246 / 236 / 228 | 0 / 4 / 7 / 4 |
| Anthracite (texte) | `#2B2B2B` | 43 / 43 / 43 | 0 / 0 / 0 / 83 |

Pour l'impression en ton direct, choisir la référence Pantone la plus proche du terracotta sur nuancier avec l'imprimeur.

**Associations autorisées**
- terracotta sur blanc ou sur sable ;
- sable sur terracotta ou sur anthracite (utiliser `observatoire-symbole-inverse.svg`, légèrement affiné pour fond sombre) ;
- noir sur blanc ;
- blanc sur photo, sur une zone calme de l'image.

## 5. Typographie
- **Titres** : Montserrat ExtraBold et SemiBold, en capitales.
- **Texte** : Open Sans.
- Les deux polices sont libres (licence SIL Open Font License) et disponibles sur Google Fonts.
- Dans les versions avec le nom, celui-ci est **vectorisé** en Montserrat : « OBSERVATOIRE » en ExtraBold,
  « DU COMMERCE » en SemiBold. Le logo s'affiche donc à l'identique partout, même sans la police installée.
- **Composition** : les deux lignes ont la même largeur, l'interligne est égal à la largeur d'un pilier, et le bloc de
  texte est centré sur la hauteur du symbole.
- La police et sa licence sont dans `fonts/`. Pour recomposer le nom :
  `python3 outils/vectoriser_nom.py fonts/Montserrat-wght.ttf final`.
- Variantes prêtes à l'emploi dans `final/` et `final/web/` : couleur, inversée, noir, blanc, terracotta, en SVG et en PNG
  de 1200 px.

## 6. À éviter
- déformer, étirer ou faire pivoter le logo ;
- le recolorer hors de la palette ;
- ajouter une ombre, un contour, un dégradé ou un effet ;
- modifier l'écart ou les proportions entre le symbole et le nom ;
- retaper le nom dans une autre police ;
- le poser sur un fond chargé sans cartouche.

## 7. Contact
Akkim Djenadi, [linkedin.com/in/adjenadi](https://www.linkedin.com/in/adjenadi/).

Avant tout dépôt de marque, faire faire une recherche d'antériorité, par exemple auprès de l'INPI.
