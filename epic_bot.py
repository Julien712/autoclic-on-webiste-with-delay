import json
import os
import re
import time
import random
import subprocess
import smtplib
import urllib.request
import requests
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
EPIC_USERNAME = CONFIG["EPIC_USERNAME"]

URL_API = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions?locale=fr&country=FR&allowCountries=FR"

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

def envoyer_alerte(sujet, corps):
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.sendmail(SMTP_EMAIL, EMAIL, f"Subject: {sujet}\n\n{corps}".encode('utf-8'))
    except Exception as e:
        print(f"[{time.ctime()}] Alerte mail non envoyée : {e}", flush=True)

def nom_jeu(url):
    return url.split("/p/")[-1].replace("-", " ").title()

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

def attendre_texte_stable(locator, stable_pendant=5, timeout=40):
    fin = time.time() + timeout
    dernier, depuis = None, time.time()
    while time.time() < fin:
        try:
            texte = locator.inner_text().strip().lower()
        except Exception:
            texte = None
        if texte != dernier:
            dernier, depuis = texte, time.time()
        elif texte and time.time() - depuis >= stable_pendant:
            return texte
        time.sleep(1)
    return dernier or ""

def appeler_api(tentatives=3):
    derniere_erreur = None
    for essai in range(1, tentatives + 1):
        try:
            reponse = requests.get(URL_API, timeout=30)
            reponse.raise_for_status()
            return reponse.json()
        except Exception as e:
            derniere_erreur = e
            print(f"[{time.ctime()}] API Epic : essai {essai}/{tentatives} échoué ({e})", flush=True)
            if essai < tentatives:
                time.sleep(10)
    raise derniere_erreur

def recuperer_urls_jeux_gratuits():
    urls = []
    try:
        donnees = appeler_api()
        elements = donnees['data']['Catalog']['searchStore']['elements']
        
        for el in elements:
            promotions = el.get('promotions')
            if not promotions: continue
            
            promos_actives = promotions.get('promotionalOffers')
            if promos_actives and len(promos_actives) > 0:
                offers = promos_actives[0].get('promotionalOffers') or []
                for offer in offers:
                    if offer.get('discountSetting', {}).get('discountPercentage') == 0:
                        slug = None
                        offer_mappings = el.get('offerMappings') or []
                        if offer_mappings and len(offer_mappings) > 0:
                            slug = offer_mappings[0].get('pageSlug')
                        if not slug:
                            catalog_mappings = el.get('catalogNs', {}).get('mappings') or []
                            if catalog_mappings and len(catalog_mappings) > 0:
                                slug = catalog_mappings[0].get('pageSlug')
                        if not slug:
                            slug = el.get('productSlug') or el.get('urlSlug')
                            if slug and slug.endswith('/home'):
                                slug = slug.replace('/home', '')
                        if slug:
                            slug = slug.strip('/')
                            urls.append(f"https://store.epicgames.com/fr/p/{slug}")
    except Exception as e:
        print(f"Erreur API Epic : {e}", flush=True)
        envoyer_alerte(
            "Bot Epic : ERREUR API", 
            f"Impossible de récupérer la liste des jeux gratuits.\n\nDétails de l'erreur : {e}"
        )
    return list(set(urls))

def simuler_comportement_humain(page):
    page.evaluate("window.scrollBy(0, 300);")
    time.sleep(random.uniform(0.8, 1.5))
    
    for _ in range(random.randint(2, 4)):
        x = random.randint(100, 700)
        y = random.randint(100, 500)
        page.mouse.move(x, y, steps=10)
        time.sleep(random.uniform(0.2, 0.5))

def executer_claim():
    attente_aleatoire = random.randint(0, 1800) if not os.isatty(0) else 0
    print(f"[{time.ctime()}] Attente aléatoire de {attente_aleatoire // 60} min avant de commencer...", flush=True)
    time.sleep(attente_aleatoire)

    urls_jeux = recuperer_urls_jeux_gratuits()
    if not urls_jeux:
        print(f"[{time.ctime()}] Aucun jeu gratuit trouvé cette semaine via l'API.", flush=True)
        return

    print(f"[{time.ctime()}] Jeux trouvés via l'API : {urls_jeux}", flush=True)

    fermer_chromium()
    process = subprocess.Popen(
        [
            "chromium",
            "--remote-debugging-port=9222",
            "--password-store=basic",
            f"--user-agent={USER_AGENT}",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "DISPLAY": ":0"}
    )

    jeux_effectivement_recuperes = []
    jeux_echoues = []
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
            page = context.pages[0] if context.pages else context.new_page()

            appliquer_override(context, page)
            context.add_init_script(WEBGL_SCRIPT)
            context.on("page", lambda nouvelle_page: appliquer_override(context, nouvelle_page))
            print(f"[{time.ctime()}] User agent Windows appliqué (Chrome {CHROME_VERSION}).", flush=True)

            for url in urls_jeux:
                url_francais = f"{url}?lang=fr"
                
                print(f"[{time.ctime()}] Go sur : {url_francais}", flush=True)
                page.goto(url_francais, timeout=90000, wait_until="domcontentloaded")
                
                print(f"[{time.ctime()}] Vérification du statut de connexion...", flush=True)
                try:
                    page.wait_for_selector('button[aria-label="Account menu"]', state="visible", timeout=60000)
                    print(f"[{time.ctime()}] Session active ! Utilisateur connecté.", flush=True)
                except:
                    print(f"[{time.ctime()}] ERREUR : Utilisateur non connecté sur Epic Games !", flush=True)
                    connexion_reussie = False
                    try:
                        bouton_connexion = page.get_by_text("Se connecter", exact=False).first
                        bouton_connexion.wait_for(state="visible", timeout=60000)
                        time.sleep(random.uniform(1.0, 2.0))
                        print(f"[{time.ctime()}] Clic sur le bouton contenant 'Se connecter'...", flush=True)
                        bouton_connexion.click(timeout=15000)

                        bouton_compte = page.get_by_text(EPIC_USERNAME, exact=True).first
                        bouton_compte.wait_for(state="visible", timeout=60000)
                        time.sleep(random.uniform(1.0, 2.0))
                        print(f"[{time.ctime()}] Clic sur le compte Epic '{EPIC_USERNAME}'...", flush=True)
                        bouton_compte.click(timeout=15000)

                        page.wait_for_selector('button[aria-label="Account menu"]', state="visible", timeout=60000)
                        print(f"[{time.ctime()}] Connexion réussie, reprise du traitement.", flush=True)
                        connexion_reussie = True
                    except Exception as e:
                        print(f"[{time.ctime()}] Connexion automatique impossible ou non confirmée : {e}", flush=True)

                    if not connexion_reussie:
                        envoyer_alerte(
                            "Bot Epic : COMPTE DÉCONNECTÉ",
                            f"La session a expiré sur le jeu :\n{url}\n\nJe patiente jusqu'à 10 minutes. Connecte-toi manuellement !"
                        )
                        try:
                            page.wait_for_selector('button[aria-label="Account menu"]', state="visible", timeout=600000)
                            print(f"[{time.ctime()}] Connexion validée, reprise du traitement.", flush=True)
                        except:
                            print(f"[{time.ctime()}] Toujours pas connecté après 10 min. Abandon.", flush=True)
                            return
                    page.goto(url_francais, timeout=90000, wait_until="domcontentloaded")
                
                deja_possede = False
                try:
                    bouton_obtenir = page.locator('button:has-text("Obtenir"), button:has-text("Dans la bibliothèque"), button:has-text("Requiert le jeu de base")').first
                    bouton_obtenir.wait_for(state="attached", timeout=60000)
                    texte_bouton = attendre_texte_stable(bouton_obtenir)
                    
                    if "dans la bibliothèque" in texte_bouton:
                        print(f"[{time.ctime()}] Déjà possédé dans la bibliothèque Epic. Pas d'alerte. Suivant.", flush=True)
                        deja_possede = True
                    elif "requiert le jeu de base" in texte_bouton:
                        print(f"[{time.ctime()}] DLC détecté sans le jeu de base (bouton désactivé). Suivant.", flush=True)
                        continue
                    elif "obtenir" not in texte_bouton:
                        print(f"[{time.ctime()}] Texte de bouton inattendu : '{texte_bouton}'. Suivant.", flush=True)
                        jeux_echoues.append((url, f"texte de bouton inattendu : '{texte_bouton}'"))
                        continue
                except Exception as e:
                    print(f"Impossible de trouver ou lire le bouton d'achat : {e}", flush=True)
                    jeux_echoues.append((url, "bouton d'achat introuvable"))
                    continue
                
                if deja_possede:
                    continue
                
                print(f"[{time.ctime()}] Nouveau jeu détecté ! Tentative d'obtention...", flush=True)
                
                bouton_obtenir.scroll_into_view_if_needed()
                simuler_comportement_humain(page)

                if "dans la bibliothèque" in bouton_obtenir.inner_text().lower():
                    print(f"[{time.ctime()}] Finalement déjà possédé (état chargé tardivement). Suivant.", flush=True)
                    continue
                
                bouton_obtenir.hover()
                time.sleep(random.uniform(1, 2))
                bouton_obtenir.click()
                print(f"[{time.ctime()}] Clic 'Obtenir' effectué. Attente du module de paiement...", flush=True)

                bouton_trouve = False
                frame_paiement = None
                popup_continuer_geree = False

                for _ in range(120):
                    if not popup_continuer_geree:
                        try:
                            bouton_incompatible = page.locator('button:has-text("Continuer")')
                            if bouton_incompatible.count() > 0 and bouton_incompatible.first.is_visible():
                                print(f"[{time.ctime()}] Popup 'Appareil non compatible' détectée. Clic sur 'Continuer'.", flush=True)
                                bouton_incompatible.first.click()
                                popup_continuer_geree = True
                                time.sleep(2)
                                continue
                        except:
                            pass

                    for frame in page.frames:
                        try:
                            root_paiement = frame.locator("#purchase-app-root")
                            if root_paiement.is_visible():
                                frame_paiement = frame
                                cible = root_paiement.locator('button:has-text("Ajouter à la bibliothèque")')
                                if cible.is_visible():
                                    print(f"[{time.ctime()}] Zone de paiement détectée ! Clic sur le bouton de validation.", flush=True)
                                    cible.scroll_into_view_if_needed()
                                    time.sleep(random.uniform(1, 2))
                                    cible.hover()
                                    time.sleep(1)
                                    cible.click()
                                    bouton_trouve = True
                                    break
                        except:
                            pass
                    if bouton_trouve:
                        break
                    time.sleep(1)

                if not bouton_trouve:
                    print(f"[{time.ctime()}] Le bouton final dans #purchase-app-root n'a pas été trouvé. Passage au suivant.", flush=True)
                    jeux_echoues.append((url, "bouton de validation du paiement introuvable"))
                    continue
                
                print(f"[{time.ctime()}] Clic de validation effectué. Analyse de l'issue de la commande...", flush=True)
                
                achat_reussi = False
                captcha_detecte = False
                popup_retractation_geree = False

                for _ in range(120):
                    try:
                        if page.locator('text="Le lanceur Epic Games est-il installé ?"').is_visible():
                            achat_reussi = True
                            break
                    except:
                        pass

                    if frame_paiement and not popup_retractation_geree:
                        try:
                            bouton_popup = frame_paiement.locator('button:has-text("J\'accepte")')
                            if bouton_popup.is_visible():
                                print(f"[{time.ctime()}] Popup de rétractation détectée. Clic sur 'J\'accepte'.", flush=True)
                                bouton_popup.hover()
                                time.sleep(random.uniform(1, 2))
                                bouton_popup.click()
                                popup_retractation_geree = True
                        except:
                            pass

                    try:
                        selectors_captcha = [
                            'iframe[src*="hcaptcha"]',
                            'iframe[src*="arkoselabs"]',
                            'iframe[title*="hCaptcha"]',
                            '#hcaptcha-challenge',
                            '#arkose'
                        ]
                        for sel in selectors_captcha:
                            loc = page.locator(sel)
                            if loc.count() > 0 and loc.first.is_visible():
                                captcha_detecte = True
                                break

                        if not captcha_detecte:
                            for frame in page.frames:
                                if any(token in frame.url for token in ["arkoselabs", "hcaptcha", "recaptcha"]):
                                    if frame.frame_element().is_visible():
                                        captcha_detecte = True
                                        break
                    except:
                        pass

                    if captcha_detecte:
                        break
                                        
                    time.sleep(1)

                if captcha_detecte:
                    print(f"[{time.ctime()}] CAPTCHA DÉTECTÉ ! J'attends jusqu'à 10 minutes.", flush=True)
                    envoyer_alerte(
                        "Bot Epic : CAPTCHA DÉTECTÉ",
                        f"Un CAPTCHA est apparu sur le jeu :\n{url}\n\nRésous-le sous 10 minutes !"
                    )
                    for _ in range(120):
                        try:
                            if page.locator('text="Le lanceur Epic Games est-il installé ?"').is_visible():
                                achat_reussi = True
                                print(f"[{time.ctime()}] CAPTCHA résolu manuellement. Validation confirmée !", flush=True)
                                break
                        except:
                            pass
                        time.sleep(5)

                if achat_reussi:
                    print(f"[{time.ctime()}] Achat validé avec succès !", flush=True)
                    jeux_effectivement_recuperes.append(url)
                else:
                    print(f"[{time.ctime()}] Échec de confirmation pour ce jeu. Passage au suivant...", flush=True)
                    raison = "CAPTCHA non résolu à temps" if captcha_detecte else "confirmation d'achat non détectée"
                    jeux_echoues.append((url, raison))

                pause = random.uniform(5, 10)
                print(f"[{time.ctime()}] Pause de {pause:.0f}s avant le traitement suivant.", flush=True)
                time.sleep(pause)
                
            if jeux_effectivement_recuperes:
                liste_noms = "\n- ".join(nom_jeu(u) for u in jeux_effectivement_recuperes)
                envoyer_alerte(
                    f"Bot Epic Games : {len(jeux_effectivement_recuperes)} jeu(x) récupéré(s) !", 
                    f"Succès ! Les jeux suivants ont été ajoutés à ta bibliothèque :\n\n- {liste_noms}"
                )

            if jeux_echoues:
                liste_echecs = "\n- ".join(f"{nom_jeu(u)} ({raison})\n  {u}" for u, raison in jeux_echoues)
                print(f"[{time.ctime()}] {len(jeux_echoues)} jeu(x) en échec.", flush=True)
                envoyer_alerte(
                    f"Bot Epic Games : {len(jeux_echoues)} jeu(x) NON récupéré(s)",
                    f"Ces jeux n'ont pas pu être récupérés, vérifie manuellement :\n\n- {liste_echecs}"
                )

            if not jeux_effectivement_recuperes and not jeux_echoues:
                print(f"[{time.ctime()}] Fin du run. Aucun nouveau jeu à récupérer (tout était déjà possédé ou non éligible).", flush=True)
                
        except Exception as e:
            print(f"[{time.ctime()}] ERREUR : {e}", flush=True)
            detail = str(e)
            if jeux_effectivement_recuperes:
                detail += "\n\nJeux récupérés avant l'erreur :\n- " + "\n- ".join(nom_jeu(u) for u in jeux_effectivement_recuperes)
            if jeux_echoues:
                detail += "\n\nJeux en échec avant l'erreur :\n- " + "\n- ".join(f"{nom_jeu(u)} ({raison})" for u, raison in jeux_echoues)
            envoyer_alerte("Bot Epic : ERREUR", detail)
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
    executer_claim()
