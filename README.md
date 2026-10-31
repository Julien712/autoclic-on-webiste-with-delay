# Script d'automatisation d'actions sur site web programmées

Ce projet fournit un script Python basé sur **Playwright** conçu pour exécuter de manière fiable une action de navigation répétitive sur une plateforme distante, tout en gérant un cycle de vie strict sur plusieurs jours.

Idéal pour les architectures légères (type Raspberry Pi ou serveurs Linux domestiques), le script pilote le **Chromium installé sur la machine** via le protocole DevTools (port 9222) et intègre des mécanismes de résilience face aux lenteurs, aux interruptions réseau et aux vérifications d'interaction.

Le dépôt contient :
* `bot_clic.py` : le script
* `config.json` : le fichier de configuration (données personnelles et compteur de jours)

## 🚀 Fonctionnalités

* **Déclenchement aléatoire :** retardement dynamique de l'exécution (jusqu'à 30 minutes) pour lisser la charge et éviter les patterns fixes d'activité. Ce délai est ignoré quand le script est lancé à la main dans un terminal.
* **Planification journalière définie :** suivi du nombre de jours restants (`remaining_days`) directement dans `config.json`. Le compteur n'est décrémenté qu'après une validation confirmée, et sa sauvegarde est sécurisée (écriture dans un fichier temporaire puis renommage) pour qu'une coupure de courant ne corrompe pas le fichier.
* **Attentes dynamiques :** le script attend que Chromium et la page soient réellement prêts (port de debug, champs du formulaire, élément de confirmation) au lieu d'utiliser des pauses fixes, ce qui le rend adapté aux machines lentes.
* **Gestion des blocages :** détection automatique d'un Captcha à l'écran, alerte par email, puis attente d'une résolution manuelle (jusqu'à environ 12 minutes).
* **Profil navigateur cohérent :** user agent Windows, Client Hints, `navigator.platform` et renderer WebGL alignés sur une même identité, configurable dans le script (`WEBGL_RENDERER`).
* **Fermeture propre de Chromium :** arrêt en douceur du navigateur avant et après chaque exécution pour que le profil et les cookies de session soient correctement sauvegardés.
* **Mode silence radio :** une fois le compteur à zéro, le script émet une alerte unique puis se désactive complètement (compteur à `-1`) sans générer de logs ni de spams d'alertes.
* **Alerting SMTP :** notifications par email en cas d'anomalie (captcha, échec de validation, erreur inattendue) ou pour signaler la fin de la mission.

⚠️ Le trousseau de clés peut être responsable de la déconnexion des sessions utilisateur (ex : gnome-keyring). Le script lance donc Chromium avec `--password-store=basic` pour l'éviter.

## 📋 Prérequis

* Linux avec une **session graphique ouverte** (le script utilise `DISPLAY=:0`). Sur un Raspberry Pi, activer l'ouverture de session automatique.
* **Chromium** installé sur la machine.
* **Python 3** et la bibliothèque Playwright.

## ⚙️ Installation

Il n'est pas nécessaire de lancer `playwright install` : le script pilote le Chromium du système.
```bash
sudo apt install chromium
python3 -m pip install --break-system-packages playwright requests
```
Placer `bot_clic.py` et `config.json` **dans le même dossier** (par exemple le Bureau), puis rendre le script exécutable :
```bash
chmod +x /home/wark/Desktop/bot_clic.py
```

## 🔧 Configuration

Les données personnelles sont dans le fichier `config.json` du dépôt, qui doit rester dans le même dossier que le script. Le script ne contient aucune donnée sensible : tu peux le remplacer ou le mettre à jour sans rien recopier.

| Clé | Rôle |
|---|---|
| `SMTP_EMAIL` | Compte Gmail qui envoie les alertes |
| `SMTP_PASSWORD` | Mot de passe d'application Gmail |
| `EMAIL` | Adresse qui reçoit les alertes, et email saisi dans le formulaire |
| `URL_CIBLE` | Lien du site |
| `CARTE_NUMERO`, `CARTE_EXPIRY`, `CARTE_CVC`, `CARTE_NOM` | Données saisies dans le formulaire |
| `remaining_days` | Nombre de jours restants, mis à jour par le script (`-1` = mode silence radio) |

Une clé manquante provoque une erreur dès le démarrage. Si `config.json` est absent ou illisible, le script s'arrête avec un message dans le log : aucun email ne peut alors partir, puisque les identifiants du serveur mail sont dans ce même fichier.

### Variables restant dans le script

| Variable | Rôle |
|---|---|
| `SELECTEUR_BOUTON` | Sélecteur CSS du bouton à cliquer |
| `SELECTEUR_SUCCES` | Sélecteur CSS de l'élément qui confirme la réussite (ex : logo de validation) |
| `WEBGL_RENDERER` | GPU annoncé au site, à faire correspondre à celui de ton PC principal |

Pour obtenir un sélecteur CSS : ouvrir Chrome sur la page, faire `Ctrl + Maj + C`, cliquer sur l'élément voulu, puis clic droit sur la ligne surlignée → *Copy* → *Copy selector*, et coller le résultat dans le script. Faire de même pour `SELECTEUR_SUCCES` sur l'élément affiché une fois l'action validée.

## 🔒 Sécurité

`config.json` est versionné dans le dépôt : il ne doit contenir que des valeurs d'exemple. Une fois rempli avec tes vraies données (mot de passe SMTP, carte), ne le publie **jamais** sur GitHub. Comme le fichier est déjà suivi par git, un `.gitignore` ne suffit pas : demande plutôt à git d'ignorer tes modifications locales.
```bash
git update-index --skip-worktree config.json
```
Cette commande empêche tes valeurs réelles d'être commitées par erreur. Pour la désactiver : `git update-index --no-skip-worktree config.json`.

## 🧪 Commandes de test et de debug

Pour tester le script manuellement (ignore le timer aléatoire) :
```bash
/usr/bin/python3 /home/wark/Desktop/bot_clic.py
```
Pour vérifier l'identité annoncée au site, mettre `https://bot.sannysoft.com/` dans `URL_CIBLE` et lancer le script : la page de test s'affiche (le script s'arrêtera ensuite faute de formulaire, c'est normal).

## ⏰ Automatisation avec Cron

Pour orchestrer le script chaque soir à une heure fixe (en laissant le script gérer son propre délai aléatoire interne), ajouter la règle suivante au `crontab` :
```bash
crontab -e
```
Ligne à ajouter tout en bas du fichier :
```bash
00 22 * * * /usr/bin/python3 -u /home/wark/Desktop/bot_clic.py >> /home/wark/Desktop/bot_clic.log 2>&1
```

## 📊 Consultation des résultats

Lire le journal de bord (les logs) :
```bash
cat /home/wark/Desktop/bot_clic.log
```
Suivre les logs en direct :
```bash
tail -f /home/wark/Desktop/bot_clic.log
```
Voir combien de jours il reste au compteur (et l'éditer) :
```bash
nano /home/wark/Desktop/config.json
```
Pour réactiver le script après la fin de la mission, remettre un nombre de jours positif dans `remaining_days` (par exemple `14`) : la valeur `-1` correspond au mode silence radio.
