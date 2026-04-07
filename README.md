# Clic automatique sur un site web avec délai
Permet de cliquer sur un bouton spécifique sur un site chaque soir à 23h pendant X jours, puis éteindre l'appareil

## Préparation de l'environnement Python

Installation de Playwright (le moteur du bot), du navigateur Chromium spécifique et des dépendances système
```bash
pip install playwright --break-system-packages
python3 -m playwright install chromium
python3 -m playwright install-deps
```
## Création des dossiers et fichiers sur le Bureau

Créer le dossier pour sauvegarder les cookies, le fichier de configuration initial (14 jours) et le fichier de script
```bash
mkdir -p /home/wark/Desktop/session_bot
echo '{"remaining_days": 14}' > /home/wark/Desktop/bot_config.json
nano /home/wark/Desktop/bot_clic.py
```
Copier coller le script : 
```python
import json
import os
import time
from playwright.sync_api import sync_playwright

URL_CIBLE = "https://example.site.com"
SELECTEUR_BOUTON = "#payment-form > div > div > div > div.FadeWrapper > div > div > div > div > div:nth-child(2) > div > button > div > span.LinkActionButton-text > div.SubmitButton-IconContainer" 
# TEST : SELECTEUR_BOUTON = "#root > div > div > div.App-Payment > div > footer > div > a > div"
CONFIG_FILE = "/home/wark/Desktop/bot_config.json"
USER_DATA_DIR = "/home/wark/Desktop/session_bot" 

def charger_compteur():
    if not os.path.exists(CONFIG_FILE):
        return 0
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        return data.get("remaining_days", 0)
def sauver_compteur(jours):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"remaining_days": jours}, f, indent=4)
def executer_clic():
    jours = charger_compteur()
    if jours <= 0:
        print("Mission accomplie (0 jours restants). Extinction du Pi.")
        time.sleep(5)
        os.system("sudo shutdown now") 
        return
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch_persistent_context(
                USER_DATA_DIR,
                headless=False,
                args=["--no-sandbox"]
            )
            page = browser.new_page()
            page.goto(URL_CIBLE, wait_until="commit", timeout=90000)
            time.sleep(180)
            page.wait_for_selector(SELECTEUR_BOUTON, state="visible", timeout=60000)
            page.click(SELECTEUR_BOUTON, force=True)
            time.sleep(180) 
            sauver_compteur(jours - 1)
            print(f"[{time.ctime()}] Clic effectué avec succès ! Nouveau solde : {jours - 1} jours.")
            time.sleep(5)
            browser.close()
        except Exception as e:
            print(f"[{time.ctime()}] ERREUR : {e}")
if __name__ == "__main__":
    executer_clic()
```
- URL_CIBLE = Lien du site
- SELECTEUR_BOUTON = Ouvrir Chrome, faire Ctrl + Maj + C, cliquer sur le bouton que tu veux, Fais un clic droit sur la ligne surlignée -> Copy -> Copy selector, puis coller dans le script
- CONFIG_FILE = fichier texte qui contient le nombres de jours
- USER_DATA_DIR = cookies de la session


## Commandes de test et de debug
Pour tester le script manuellement (le DISPLAY=:0 est crucial pour usage avec interface graphique)
```bash
export DISPLAY=:0 && python3 /home/wark/Desktop/bot_clic.py
```
Pour vérifier que l'utilisateur 'wark' peut éteindre l'appareil sans mot de passe
```bash
sudo -l
```
## Automatisation avec Cron
```bash
crontab -e
```
Ligne à ajoutée tout en bas du fichier :
```bash
00 23 * * * DISPLAY=:0 /usr/bin/python3 /home/wark/Desktop/bot_clic.py >> /home/wark/Desktop/log_bot.txt 2>&1
```
## Consultation des résultats
Lire le journal de bord (les logs)
```bash
cat /home/wark/Desktop/log_bot.txt
```
Voir combien de jours il reste au compteur (et l'éditer) 
```bash
nano /home/wark/Desktop/bot_config.json
```


