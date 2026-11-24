# Mettre l'Observatoire du Commerce en ligne

## Pourquoi pas directement sur Vercel

Vercel n'exécute Python que sous forme de fonctions courtes, lancées à chaque requête puis arrêtées. Streamlit, lui,
a besoin d'un serveur qui tourne en continu et garde une connexion ouverte (WebSocket) avec chaque visiteur.
**L'application ne peut donc pas tourner sur Vercel.**

La solution la plus simple et gratuite : **Streamlit Community Cloud**, qui déploie directement depuis le dépôt GitHub.
Vercel reste utile pour donner à l'application une adresse personnalisée (étape 3, facultative).

## 1. Déployer sur Streamlit Community Cloud (≈ 5 minutes)

1. Aller sur **https://share.streamlit.io** et se connecter avec le compte GitHub `akkim-djenadi`.
2. Accepter que Streamlit accède aux **dépôts privés** : il en a besoin, car le dépôt `observatoire-du-commerce` est privé.
3. Cliquer sur **Create app**, puis **Deploy a public app from GitHub**.
4. Remplir :
   - **Repository** : `akkim-djenadi/observatoire-du-commerce`
   - **Branch** : `main`
   - **Main file path** : `app.py`
   - **App URL** : par exemple `observatoire-du-commerce` (l'adresse devient `https://observatoire-du-commerce.streamlit.app`)
5. Dans **Advanced settings**, choisir **Python 3.12**. Aucun secret n'est nécessaire : toutes les sources sont
   publiques.
6. Cliquer sur **Deploy**. La première installation prend 2 à 3 minutes.

**Ensuite**, chaque `git push` sur la branche `main` met automatiquement l'application à jour.

## 2. Bon à savoir

- **Visibilité** : le code reste privé, mais l'application peut être ouverte à tous ou réservée à des personnes
  invitées par e-mail (menu **Settings › Sharing** de l'application), selon les limites de l'offre gratuite.
- **Mise en veille** : sans visite pendant un moment, l'application s'endort. Le visiteur suivant clique sur
  « Yes, get this app back up » et elle redémarre en une trentaine de secondes.
- **Première recherche plus lente** : la mémoire des fiches entreprises (`cache/`) est vidée à chaque redémarrage.
  La première recherche sur 6 mois prend alors 1 à 2 minutes, les suivantes sont immédiates.

## 3. Facultatif : une adresse personnalisée avec Vercel

Streamlit Community Cloud ne gère pas les noms de domaine personnalisés. Vercel peut en revanche rediriger votre
domaine (par exemple `observatoire-commerce.fr`) vers l'application.

1. Créer un dossier séparé, par exemple `observatoire-redirection/`, contenant ce seul fichier `vercel.json` :
   ```json
   {
     "redirects": [
       { "source": "/(.*)", "destination": "https://observatoire-du-commerce.streamlit.app", "permanent": false }
     ]
   }
   ```
2. Le publier avec l'outil en ligne de commande de Vercel (il demande de se connecter au premier lancement) :
   ```bash
   npx vercel deploy --prod
   ```
3. Dans le tableau de bord Vercel, **Settings › Domains**, ajouter votre domaine et suivre les indications DNS.

Les visiteurs qui tapent votre domaine arrivent ainsi sur l'application.

## 4. Lancer l'application en local

```bash
pip3 install -r requirements-dev.txt
python3 -m streamlit run app.py
```
