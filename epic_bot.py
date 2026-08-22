import os
import time
import random
import subprocess
import smtplib
import requests
from playwright.sync_api import sync_playwright

URL_API = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions?locale=fr&country=FR&allowCountries=FR"
SELECTEUR_BOUTON_OBTENIR = '[data-testid="purchase-cta-button"]'

def envoyer_alerte(sujet, corps):
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login("smtp@email.com", "password")
            s.sendmail("smtp@email.com", "dest@email.com", f"Subject: {sujet}\n\n{corps}".encode('utf-8'))
    except: 
        pass

def recuperer_urls_jeux_gratuits():
    urls = []
    try:
        reponse = requests.get(URL_API, timeout=30)
        donnees = reponse.json()
        elements = donnees['data']['Catalog']['searchStore']['elements']
        
        for el in elements:
            promotions = el.get('promotions')
            if not promotions: continue
            
            promos_actives = promotions.get('promotionalOffers')
            if promos_actives and len(promos_actives) > 0:
                offers = promos_actives[0].get('promotionalOffers')
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

def executer_claim():
    attente_aleatoire = random.randint(0, 1800) if not os.isatty(0) else 0
    print(f"[{time.ctime()}] Attente aléatoire de {attente_aleatoire // 60} min avant de commencer...", flush=True)
    time.sleep(attente_aleatoire)

    urls_jeux = recuperer_urls_jeux_gratuits()
    if not urls_jeux:
        print(f"[{time.ctime()}] Aucun jeu gratuit trouvé cette semaine via l'API.", flush=True)
        return

    print(f"[{time.ctime()}] Jeux trouvés via l'API : {urls_jeux}", flush=True)

    os.system("killall -9 chromium")
    time.sleep(3)
    process = subprocess.Popen(
        ["chromium", "--remote-debugging-port=9222","--password-store=basic"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "DISPLAY": ":0"}
    )
    time.sleep(10)

    jeux_effectivement_recuperes = []
    browser = None
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = context.pages[0]

            for url in urls_jeux:
                url_francais = f"{url}?lang=fr"
                
                print(f"[{time.ctime()}] Go sur : {url_francais}", flush=True)
                page.goto(url_francais, timeout=60000)
                
                print(f"[{time.ctime()}] Page chargée. Longue pause...", flush=True)
                time.sleep(60)

                print(f"[{time.ctime()}] Vérification du statut de connexion...", flush=True)
                try:
                    page.wait_for_selector('button[aria-label="Account menu"]', state="visible", timeout=10000)
                    print(f"[{time.ctime()}] Session active ! Utilisateur connecté.", flush=True)
                except:
                    print(f"[{time.ctime()}] ERREUR : Utilisateur non connecté sur Epic Games !", flush=True)
                    envoyer_alerte(
                        "Bot Epic : COMPTE DÉCONNECTÉ",
                        f"Le bot a détecté que ta session a expiré alors qu'il traitait le jeu :\n{url_francais}\n\nConnecte-toi manuellement sur le Raspberry Pi."
                    )
                    return
                
                deja_possede = False
                try:
                    page.wait_for_selector(SELECTEUR_BOUTON_OBTENIR, state="attached", timeout=10000)
                    texte_bouton = page.locator(SELECTEUR_BOUTON_OBTENIR).inner_text().lower()
                    
                    if "dans la bibliothèque" in texte_bouton:
                        print(f"[{time.ctime()}] Déjà possédé dans la bibliothèque Epic. Pas d'alerte. Suivant.", flush=True)
                        deja_possede = True
                    elif "requiert le jeu de base" in texte_bouton:
                        print(f"[{time.ctime()}] DLC détecté sans le jeu de base (bouton désactivé). Suivant.", flush=True)
                        continue
                except Exception as e:
                    print(f"Impossible de trouver ou lire le bouton d'achat : {e}", flush=True)
                    envoyer_alerte(
                        "Bot Epic : BOUTON INTROUVABLE", 
                        f"Le bouton d'achat n'a pas pu être détecté ou lu sur la page du jeu :\n{url_francais}"
                    )
                    continue
                
                if deja_possede:
                    continue
                
                print(f"[{time.ctime()}] Nouveau jeu détecté ! Tentative d'obtention...", flush=True)
                page.hover(SELECTEUR_BOUTON_OBTENIR)
                time.sleep(2)
                page.click(SELECTEUR_BOUTON_OBTENIR)
                print(f"[{time.ctime()}] Clic 'Obtenir' effectué. Attente du module de paiement...", flush=True)
                time.sleep(60)
                try:
                    bouton_incompatible = page.locator('button:has-text("Continuer")')
                    if bouton_incompatible.is_visible(timeout=5000):
                        print(f"[{time.ctime()}] Popup 'Appareil non compatible' détectée. Clic sur 'Continuer'.", flush=True)
                        bouton_incompatible.click()
                        time.sleep(30)
                except:
                    pass

                bouton_trouve = False
                frame_paiement = None
                
                for _ in range(60):
                    for frame in page.frames:
                        try:
                            root_paiement = frame.locator("#purchase-app-root")
                            if root_paiement.is_visible():
                                frame_paiement = frame
                                cible = root_paiement.locator('button:has-text("Ajouter à la bibliothèque")')
                                if cible.is_visible():
                                    print(f"[{time.ctime()}] Zone de paiement détectée ! Clic sur le bouton de validation.", flush=True)
                                    cible.hover()
                                    time.sleep(2)
                                    cible.click()
                                    bouton_trouve = True
                                    break
                        except:
                            pass
                    if bouton_trouve:
                        break
                    time.sleep(1)

                if not bouton_trouve:
                    raise Exception("Le bouton final dans #purchase-app-root n'a pas été trouvé.")
                
                print(f"[{time.ctime()}] Clic de validation effectué. Pause pour laisser l'interface s'ajuster...", flush=True)
                time.sleep(60)

                print(f"[{time.ctime()}] Premier clic effectué. Attente de la popup de rétractation (Max 30s)...", flush=True)
                popup_validee = False
                
                for _ in range(60):
                    try:
                        bouton_popup = frame_paiement.locator('button:has-text("J\'accepte")')
                        if bouton_popup.is_visible():
                            print(f"[{time.ctime()}] Popup de rétractation détectée. Clic sur 'J'accepte'.", flush=True)
                            bouton_popup.hover()
                            time.sleep(2)
                            bouton_popup.click()
                            popup_validee = True
                            break
                    except:
                        pass
                    time.sleep(1)

                if not popup_validee:
                    raise Exception("La popup de rétractation obligatoire (bouton 'J'accepte') n'est pas apparue.")

                print(f"[{time.ctime()}] Achat validé avec succès !", flush=True)
                jeux_effectivement_recuperes.append(url)

                print(f"[{time.ctime()}] Longue pause de validation...", flush=True)
                time.sleep(60)
                print(f"[{time.ctime()}] Fin de la pause. Passage au traitement suivant.", flush=True)
                
            if jeux_effectivement_recuperes:
                noms_jeux = [url.split("/p/")[-1].replace("-", " ").title() for url in jeux_effectivement_recuperes]
                liste_noms = "\n- ".join(noms_jeux)
                envoyer_alerte(
                    f"Bot Epic Games : {len(jeux_effectivement_recuperes)} jeu(x) récupéré(s) !", 
                    f"Succès ! Les jeux suivants ont été ajoutés à ta bibliothèque :\n\n- {liste_noms}"
                )
            else:
                print(f"[{time.ctime()}] Fin du run. Aucun email envoyé car aucun nouveau jeu n'a été récupéré (tout était déjà possédé).", flush=True)
                
        except Exception as e:
            print(f"[{time.ctime()}] ERREUR : {e}", flush=True)
            envoyer_alerte("Bot Epic : ERREUR", str(e))
        finally:
            if browser:
                try:
                    browser.close()
                except:
                    pass
            if process.poll() is None:
                process.terminate()

if __name__ == "__main__":
    executer_claim()
