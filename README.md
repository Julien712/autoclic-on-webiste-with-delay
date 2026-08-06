# Script d'automatisation d'actions sur site web programmées

Ce projet fournit un script Python robuste basé sur **Playwright** conçu pour exécuter de manière fiable une action de navigation répétitive sur une plateforme distante, tout en gérant un cycle de vie strict sur plusieurs jours. 

Idéal pour les architectures légères (type Raspberry Pi ou serveurs Linux domestiques), le script intègre des mécanismes de résilience face aux interruptions réseau et aux vérifications d'interaction.

## 🚀 Fonctionnalités

* **Déclenchement Aléatoire :** Retardement dynamique de l'exécution (jusqu'à 30 minutes) pour lisser la charge et éviter les patterns fixes d'activité.
* **Planification journalière définie :** Suivi strict du nombre de jours d'exécution restants via un fichier de configuration JSON local.
* **Gestion des blocages :** Détection automatique de la présence d'un Captcha à l'écran pour mettre le script en pause et permettre une résolution manuelle.
* **Mode Silence Radio :** Une fois le compteur à zéro, le script émet une alerte unique puis se désactive complètement en arrière-plan sans générer de logs ni de spams d'alertes.
* **Alerting SMTP :** Notifications par email en cas d'anomalie détectée (perte de session, erreur de validation) ou pour signaler la fin de la mission.

⚠️ Le trousseau de clés peut être responsable de la déconnexion des sessions utilisateur (ex : gnome-keyring).

## Préparation de l'environnement Python

Installation de Playwright (le moteur du bot), du navigateur Chromium spécifique et des dépendances système
```bash
python3 -m pip install --break-system-packages playwright requests
python3 -m playwright install-deps
```
## Création des dossiers et fichiers sur le Bureau

Créer le fichier de configuration initial (14 jours) et le fichier de script
```bash
echo '{"remaining_days": 14}' > /home/wark/Desktop/bot_config.json
nano /home/wark/Desktop/bot_clic.py
```
Copier coller le script : 
```python
import json
import os
import time
import random
import subprocess
import smtplib
from playwright.sync_api import sync_playwright

URL_CIBLE = "https://exemple.site.com"
SELECTEUR_BOUTON = "#payment-form > div > div > div > div.FadeWrapper > div > div > div > div > div:nth-child(2) > div > button > div > span.LinkActionButton-text > div.SubmitButton-IconContainer" 
SELECTEUR_SUCCES = "#root > div > div > div.App-Payment.App-Payment--success > div.PaymentSuccess.flex-container.direction-column.justify-content-center.align-items-center > div > div.PaymentSuccess-header.flex-container.direction-column.align-items-center > div > svg > circle"
CONFIG_FILE = "/home/wark/Desktop/bot_config.json"
MON_EMAIL = "exemple@gmail.com"

def charger_compteur():
    if not os.path.exists(CONFIG_FILE):
        return 0
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        return data.get("remaining_days", 0)
def sauver_compteur(jours):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"remaining_days": jours}, f, indent=4)
def envoyer_alerte(sujet, corps):
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login("smtp@email.com", "password")
            s.sendmail("smtp@email.com", "dest@email.com", f"Subject: {sujet}\n\n{corps}".encode('utf-8'))
    except: pass
def executer_clic():
    attente_aleatoire = random.randint(0, 1800) if not os.isatty(0) else 0
    print(f"[{time.ctime()}] Attente aléatoire de {attente_aleatoire // 60} min avant de commencer...", flush=True)
    time.sleep(attente_aleatoire)
    jours = charger_compteur()
    if jours == -1:
        return
    if jours <= 0:
        print("Mission accomplie (0 jours restants).")
        envoyer_alerte("Mission Terminee", "Le compteur est a 0. Le bot se met en silence jusqu'a recharge.")
        sauver_compteur(-1)
        time.sleep(15)
        return
    os.system("killall -9 chromium")
    time.sleep(3)
    process = subprocess.Popen(["chromium-browser", URL_CIBLE, "--remote-debugging-port=9222"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "DISPLAY": ":0"})
    time.sleep(10)
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            if not context.pages: raise Exception("Aucun onglet detecte")
            page = context.pages[0]
            time.sleep(120)
            if MON_EMAIL not in page.content():
                print(f"[{time.ctime()}] Erreur : Email introuvable.")
                envoyer_alerte("Bot : Non connecté", f"L'email {MON_EMAIL} est introuvable sur la page. Session expirée ?")
                browser.close()
                return
            page.wait_for_selector(SELECTEUR_BOUTON, state="visible", timeout=60000)
            page.hover(SELECTEUR_BOUTON)
            time.sleep(2)
            page.click(SELECTEUR_BOUTON, force=True)
            print(f"[{time.ctime()}] Clic effectué. Attente du traitement...")
            time.sleep(120)
            captcha_detecte = False
            html_complet = page.content()
            if "LightboxModalBody" in html_complet or "hcaptcha-inner" in html_complet:
                captcha_detecte = True
            if captcha_detecte:
                print(f"[{time.ctime()}] Captcha détecté ! Pause de 10 minutes pour résolution manuelle...")
                envoyer_alerte("Bot : CAPTCHA DETECTE", "Un hCaptcha bloque la validation. Viens cocher la case sur le RPi, tu as 10 minutes.")
                time.sleep(600)
            if page.locator(SELECTEUR_SUCCES).is_visible():
                sauver_compteur(jours - 1)
                print(f"[{time.ctime()}] Clic validé avec succès ! Nouveau solde : {jours - 1} jours.")
            else:
                print(f"[{time.ctime()}] Échec : Logo de confirmation introuvable.")
                envoyer_alerte("Bot : Échec Validation", "Le bouton a été cliqué mais le logo check vert de confirmation n'est pas apparu.")
                browser.close()
                return
            time.sleep(5)
            browser.close()
        except Exception as e:
            erreur_msg = f"Erreur lors du clic : {e}"
            print(f"[{time.ctime()}] ERREUR : {e}")
            envoyer_alerte("Bot : ERREUR DETECTEE", erreur_msg)
        finally:
            if process.poll() is None:
                process.terminate()
if __name__ == "__main__":
    executer_clic()
```
- URL_CIBLE = Lien du site
- SELECTEUR_BOUTON = Ouvrir Chrome, faire Ctrl + Maj + C, cliquer sur le bouton que tu veux, Fais un clic droit sur la ligne surlignée -> Copy -> Copy selector, puis coller dans le script
- CONFIG_FILE = fichier texte qui contient le nombres de jours

Le rendre exécutable : 
```bash
chmod +x /home/wark/Desktop/bot_clic.py
```
## Commandes de test et de debug
Pour tester le script manuellement (ignore le timer aléatoire)
```bash
/usr/bin/python3 /home/wark/Desktop/bot_clic.py
```
Pour vérifier que l'utilisateur 'wark' peut éteindre l'appareil sans mot de passe
```bash
sudo -l
```
## Automatisation avec Cron
Pour orchestrer le script chaque soir à une heure fixe (en laissant le script gérer son propre délai aléatoire interne), ajoutez la règle suivante à votre `crontab` :
```bash
crontab -e
```
Ligne à ajoutée tout en bas du fichier :
```bash
00 22 * * * /usr/bin/python3 -u /home/wark/Desktop/clic_bot.py >> /home/wark/Desktop/clic_bot.log 2>&1
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
