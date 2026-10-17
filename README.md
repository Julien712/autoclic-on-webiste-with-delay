# Script d'automatisation d'actions sur site web programmées

Ce projet fournit un script Python basé sur **Playwright** conçu pour exécuter de manière fiable une action de navigation répétitive sur une plateforme distante, tout en gérant un cycle de vie strict sur plusieurs jours.

Idéal pour les architectures légères (type Raspberry Pi ou serveurs Linux domestiques), le script pilote le **Chromium installé sur la machine** via le protocole DevTools (port 9222) et intègre des mécanismes de résilience face aux lenteurs, aux interruptions réseau et aux vérifications d'interaction.

## 🚀 Fonctionnalités

* **Déclenchement aléatoire :** Retardement dynamique de l'exécution (jusqu'à 30 minutes) pour lisser la charge et éviter les patterns fixes d'activité. Ce délai est ignoré quand le script est lancé à la main dans un terminal.
* **Planification journalière définie :** Suivi strict du nombre de jours d'exécution restants via un fichier de configuration JSON local, décrémenté uniquement après une validation confirmée.
* **Attentes dynamiques :** Le script attend que Chromium et la page soient réellement prêts (port de debug, champs du formulaire, élément de confirmation) au lieu d'utiliser des pauses fixes, ce qui le rend adapté aux machines lentes.
* **Gestion des blocages :** Détection automatique d'un Captcha à l'écran, alerte par email, puis attente d'une résolution manuelle (jusqu'à environ 12 minutes).
* **Profil navigateur cohérent :** User agent Windows, Client Hints, `navigator.platform` et renderer WebGL alignés sur une même identité, configurable dans le script (voir `WEBGL_RENDERER`).
* **Fermeture propre de Chromium :** Arrêt en douceur du navigateur avant et après chaque exécution pour que le profil et les cookies de session soient correctement sauvegardés.
* **Mode silence radio :** Une fois le compteur à zéro, le script émet une alerte unique puis se désactive complètement (compteur à `-1`) sans générer de logs ni de spams d'alertes.
* **Alerting SMTP :** Notifications par email en cas d'anomalie (captcha, échec de validation, erreur inattendue) ou pour signaler la fin de la mission.

⚠️ Le trousseau de clés peut être responsable de la déconnexion des sessions utilisateur (ex : gnome-keyring). Le script lance donc Chromium avec `--password-store=basic` pour l'éviter.

## 📋 Prérequis

* Linux avec une **session graphique ouverte** (le script utilise `DISPLAY=:0`). Sur un Raspberry Pi, activer l'ouverture de session automatique.
* **Chromium** installé sur la machine.
* **Python 3** et la bibliothèque Playwright.

## ⚙️ Préparation de l'environnement

Installation de Chromium et de Playwright. Il n'est pas nécessaire de lancer `playwright install` : le script pilote le Chromium du système.
```bash
sudo apt install chromium
python3 -m pip install --break-system-packages playwright
```

## 📁 Création des dossiers et fichiers sur le Bureau

Créer le fichier de configuration initial (14 jours) et le fichier de script :
```bash
echo '{"remaining_days": 14}' > /home/wark/Desktop/bot_config.json
nano /home/wark/Desktop/bot_clic.py
```
Télécharger ou importer le script `bot_clic.py`, puis le rendre exécutable :
```bash
chmod +x /home/wark/Desktop/bot_clic.py
```

## 🔧 Configuration

Variables à renseigner en haut du script :

| Variable | Rôle |
|---|---|
| `URL_CIBLE` | Lien du site |
| `SELECTEUR_BOUTON` | Sélecteur CSS du bouton à cliquer |
| `SELECTEUR_SUCCES` | Sélecteur CSS de l'élément qui confirme la réussite (ex : logo de validation) |
| `CONFIG_FILE` | Fichier JSON qui contient le nombre de jours restants |
| `FORM_EMAIL`, `CARTE_*` | Données saisies dans le formulaire |
| `WEBGL_RENDERER` | GPU annoncé au site, à faire correspondre à celui de ton PC principal |

Pour obtenir un sélecteur CSS : ouvrir Chrome sur la page, faire `Ctrl + Maj + C`, cliquer sur l'élément voulu, puis clic droit sur la ligne surlignée → *Copy* → *Copy selector*, et coller le résultat dans le script. Faire de même pour `SELECTEUR_SUCCES` sur l'élément affiché une fois l'action validée.

Les identifiants du serveur mail (fonction `envoyer_alerte`) sont à renseigner dans le script. Avec Gmail, utiliser un **mot de passe d'application**.

## 🔒 Sécurité

Le script contient des données sensibles (mot de passe SMTP, données du formulaire). Pour les protéger :

* Ne **jamais** publier le script rempli sur GitHub : garder le dépôt privé, ou ne versionner qu'une copie avec des valeurs vides.
* Restreindre les droits du fichier : `chmod 600 /home/wark/Desktop/bot_clic.py`.
* Ne pas partager les logs sans les relire.

## 🧪 Commandes de test et de debug

Pour tester le script manuellement (ignore le timer aléatoire) :
```bash
/usr/bin/python3 /home/wark/Desktop/bot_clic.py
```

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
nano /home/wark/Desktop/bot_config.json
```
Pour réactiver le script après la fin de la mission, remettre un nombre de jours positif (par exemple `{"remaining_days": 14}`) : la valeur `-1` correspond au mode silence radio.
