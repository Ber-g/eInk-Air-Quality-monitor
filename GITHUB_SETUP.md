# 🚀 Configuration GitHub

## Étapes pour sauvegarder votre projet sur GitHub

### 1. Créer un dépôt sur GitHub

1. Allez sur [GitHub.com](https://github.com)
2. Cliquez sur le bouton "+" en haut à droite
3. Sélectionnez "New repository"
4. Nom du dépôt : `eInk-Air-Quality-monitor`
5. Description : `Moniteur de qualité de l'air pour Raspberry Pi avec écran e-ink`
6. Laissez "Public" (gratuit)
7. **NE PAS** cocher "Add a README file" (on en a déjà un)
8. Cliquez sur "Create repository"

### 2. Connecter votre projet local à GitHub

Exécutez ces commandes dans le terminal (dans le dossier du projet) :

```bash
# Ajouter l'origine GitHub (remplacez VOTRE_NOM_UTILISATEUR)
git remote add origin https://github.com/VOTRE_NOM_UTILISATEUR/eInk-Air-Quality-monitor.git

# Pousser le code vers GitHub
git branch -M main
git push -u origin main
```

### 3. Vérifier que tout fonctionne

1. Rafraîchissez la page GitHub
2. Vous devriez voir tous vos fichiers
3. Le README.md s'affiche automatiquement

### 4. Pour les futures modifications

Chaque fois que vous modifiez le code :

```bash
# Ajouter les fichiers modifiés
git add .

# Créer un commit avec un message descriptif
git commit -m "Description de ce que vous avez changé"

# Envoyer vers GitHub
git push
```

### 5. Conseils pour bien utiliser Git

- **Commits fréquents** : Faites des commits souvent avec des messages clairs
- **Messages descriptifs** : "Ajout support e-ink" plutôt que "modif"
- **Testez avant de commiter** : Vérifiez que ça fonctionne
- **Sauvegardez régulièrement** : `git push` souvent

## 🆘 En cas de problème

Si vous avez des erreurs :

1. **Erreur d'authentification** : GitHub demande un token
   - Allez dans Settings > Developer settings > Personal access tokens
   - Créez un token avec les permissions "repo"
   - Utilisez ce token comme mot de passe

2. **Conflits** : Si vous modifiez sur plusieurs ordinateurs
   - `git pull` avant de faire des modifications
   - Résolvez les conflits si nécessaire

3. **Oubli de .env** : Le fichier .env n'est pas sauvegardé (c'est normal pour la sécurité)
   - Recréez-le avec `cp env_example.txt .env`
   - Ajoutez votre clé API
