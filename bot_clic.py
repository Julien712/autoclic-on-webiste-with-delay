import json
import os
import re
import time
import random
import subprocess
import smtplib
import urllib.request
from playwright.sync_api import sync_playwright

CHEMIN_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

try:
    with open(CHEMIN_CONFIG, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except Exception as e:
    raise SystemExit(f"[{time.ctime()}] ERREUR : Impossible de lire config.json : {e}")

SMTP_EMAIL = CONFIG["SMTP_EMAIL"]
SMTP_PASSWORD = CONFIG["SMTP_PASSWORD"]
EMAIL = CONFIG["EMAIL"]
URL_CIBLE = CONFIG["URL_CIBLE"]
SELECTEUR_BOUTON = "#payment-form > div > div > div > div.PaymentForm-confirmPaymentContainer.mt5.flex-item.width-grow > div > div:nth-child(3) > div > button"
SELECTEUR_SUCCES = "#root > div > div > div.App-Payment.App-Payment--success > div.PaymentSuccess.flex-container.direction-column.justify-content-center.align-items-center > div > div.PaymentSuccess-header.flex-container.direction-column.align-items-center > div > svg > circle"

CARTE_NUMERO = CONFIG["CARTE_NUMERO"]
CARTE_EXPIRY = CONFIG["CARTE_EXPIRY"]
CARTE_CVC = CONFIG["CARTE_CVC"]
CARTE_NOM = CONFIG["CARTE_NOM"]

def detecter_version_chromium():
    try:
        sortie = subprocess.check_output(["chromium", "--version"], text=True, timeout=10)
        return re.search(r"(\d+)\.\d+\.\d+\.\d+", sortie).group(1)
    except Exception:
        return "124"

CHROME_VERSION = detecter_version_chromium()
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/{CHROME_VERSION}.0.0.0 Safari/537.36"
)
BRANDS = [
    {"brand": "Chromium", "version": CHROME_VERSION},
    {"brand": "Google Chrome", "version": CHROME_VERSION},
    {"brand": "Not-A.Brand", "version": "99"},
]

WEBGL_VENDOR = "Google Inc. (NVIDIA)"
WEBGL_RENDERER = "ANGLE (NVIDIA, NVIDIA GeForce RTX 5080 (0x00002C02) Direct3D11 vs_5_0 ps_5_0, D3D11)"

WEBGL_SCRIPT = """
(() => {
  const VENDOR = %s;
  const RENDERER = %s;
  const patch = (proto) => {
    if (!proto) return;
    const original = proto.getParameter;
    proto.getParameter = function (p) {
      if (p === 37445) return VENDOR;
      if (p === 37446) return RENDERER;
      return original.call(this, p);
    };
  };
  patch(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
  patch(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
})();
""" % (json.dumps(WEBGL_VENDOR), json.dumps(WEBGL_RENDERER))

def appliquer_override(context, page):
    try:
        cdp = context.new_cdp_session(page)
        cdp.send("Emulation.setUserAgentOverride", {
            "userAgent": USER_AGENT,
            "platform": "Win32",
            "userAgentMetadata": {
                "brands": BRANDS,
                "fullVersionList": [
                    {"brand": b["brand"], "version": f"{CHROME_VERSION}.0.0.0"} for b in BRANDS
                ],
                "platform": "Windows",
                "platformVersion": "10.0.0",
                "architecture": "x86",
                "model": "",
                "mobile": False,
            },
        })
    except Exception as e:
        print(f"[{time.ctime()}] Override impossible sur un onglet : {e}", flush=True)

def fermer_chromium():
    subprocess.run(["pkill", "-x", "chromium"], check=False)
    for _ in range(15):
        if subprocess.run(["pgrep", "-x", "chromium"], capture_output=True).returncode != 0:
            return
        time.sleep(1)
    print(f"[{time.ctime()}] Chromium ne se ferme pas, arrêt forcé.", flush=True)
    subprocess.run(["pkill", "-9", "-x", "chromium"], check=False)
    time.sleep(2)

def attendre_chromium(timeout=90):
    debut = time.time()
    while time.time() - debut < timeout:
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False

def charger_compteur():
    with open(CHEMIN_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f).get("remaining_days", 0)

def sauver_compteur(jours):
    with open(CHEMIN_CONFIG, "r", encoding="utf-8") as f:
        donnees = json.load(f)
    donnees["remaining_days"] = jours
    tmp = CHEMIN_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CHEMIN_CONFIG)

def envoyer_alerte(sujet, corps):
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.sendmail(SMTP_EMAIL, EMAIL, f"Subject: {sujet}\n\n{corps}".encode('utf-8'))
    except Exception as e:
        print(f"[{time.ctime()}] Alerte mail non envoyée : {e}", flush=True)

def remplir(page, selecteur, valeur):
    champ = page.locator(selecteur)
    champ.wait_for(state="visible", timeout=120000)
    time.sleep(3)
    champ.click()
    time.sleep(1)
    champ.press_sequentially(valeur, delay=random.randint(150, 300))
    time.sleep(random.uniform(2, 4))

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
    fermer_chromium()
    process = subprocess.Popen(
        [
            "chromium",
            "about:blank",
            "--remote-debugging-port=9222",
            "--password-store=basic",
            f"--user-agent={USER_AGENT}",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "DISPLAY": ":0"}
    )
    browser = None
    with sync_playwright() as p:
        try:
            if not attendre_chromium():
                raise Exception("Chromium n'a pas démarré (port 9222 injoignable).")
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            for _ in range(30):
                if context.pages:
                    break
                time.sleep(0.5)
            if not context.pages:
                raise Exception("Aucun onglet detecte")
            page = context.pages[0]
            page.set_default_timeout(120000)
            appliquer_override(context, page)
            context.add_init_script(WEBGL_SCRIPT)
            context.on("page", lambda nouvelle_page: appliquer_override(context, nouvelle_page))
            print(f"[{time.ctime()}] User agent Windows appliqué (Chrome {CHROME_VERSION}).", flush=True)
            page.goto(URL_CIBLE, wait_until="domcontentloaded")
            page.wait_for_selector("#email", state="visible")
            remplir(page, "#email", EMAIL)
            page.keyboard.press("Tab")
            time.sleep(5)
            page.keyboard.press("Enter")
            time.sleep(10)
            remplir(page, "#cardNumber", CARTE_NUMERO)
            remplir(page, "#cardExpiry", CARTE_EXPIRY)
            remplir(page, "#cardCvc", CARTE_CVC)
            remplir(page, "#billingName", CARTE_NOM)
            page.wait_for_selector(SELECTEUR_BOUTON, state="visible", timeout=120000)
            page.hover(SELECTEUR_BOUTON)
            time.sleep(3)
            page.click(SELECTEUR_BOUTON, force=True)
            print(f"[{time.ctime()}] Clic effectué. Attente du traitement...", flush=True)
            succes = False
            alerte_captcha = False
            for _ in range(375):
                if page.locator(SELECTEUR_SUCCES).is_visible():
                    succes = True
                    break
                if not alerte_captcha:
                    html = page.content()
                    if "LightboxModalBody" in html or "hcaptcha-inner" in html:
                        alerte_captcha = True
                        print(f"[{time.ctime()}] Captcha détecté !", flush=True)
                        envoyer_alerte("Bot : CAPTCHA DETECTE", "Un hCaptcha bloque la validation. Viens cocher la case sur le RPi.")
                time.sleep(2)
            if succes:
                sauver_compteur(jours - 1)
                print(f"[{time.ctime()}] Clic validé avec succès ! Nouveau solde : {jours - 1} jours.")
                time.sleep(5)
            else:
                print(f"[{time.ctime()}] Échec : Logo de confirmation introuvable.")
                envoyer_alerte("Bot : Échec Validation", "Le bouton a été cliqué mais le logo de confirmation n'est pas apparu. Vérifie manuellement avant le prochain passage.")
        except Exception as e:
            erreur_msg = f"Erreur lors du clic : {e}"
            print(f"[{time.ctime()}] ERREUR : {e}")
            envoyer_alerte("Bot : ERREUR DETECTEE", erreur_msg)
        finally:
            if browser:
                try:
                    browser.close()
                except:
                    pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()

if __name__ == "__main__":
    executer_clic()
