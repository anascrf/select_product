# pip install streamlit selenium webdriver-manager

import time
import io
from typing import List
import os, subprocess ,streamlit as st
import warnings

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def make_driver(headless: bool = True):

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1600,1000")

    # Pointer vers le binaire système de Chromium installé par packages.txt
    for path in ("/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if os.path.exists(path):
            opts.binary_location = path
            break

    # 👇 Laisser Selenium Manager gérer le bon chromedriver
    # (ne PAS passer de Service ni utiliser webdriver-manager ici)
    driver = webdriver.Chrome(options=opts)
    return driver


# --------- CONFIG PAR DÉFAUT (modifiables dans l'UI) ----------
LOGIN_URL_DEF = "https://legendre.3magroup.com/Identification/Connexion?"
BASE_URL_DEF  = "https://legendre.3magroup.com"
ARTICLES_DEF = [
    "EAD_CP_COURS_FR_1",
    "_CP_COURS_FR_2",
    "_CP_COURS_FR_3",
    "_CP_COURS_MA_1",
    "_CP_COURS_MA_2",
    "_CP_COURS_MA_3",
    "_CP_COURS_DDM_1",
    "_CP_COURS_DDM_2",
    "_CP_COURS_DDM_3",
    "_CP_COREX_FR_1",
    "_CP_COREX_FR_2",
    "_CP_COREX_FR_3",
    "_CP_COREX_MA_1",
    "_CP_COREX_MA_2",
    "_CP_COREX_MA_3",
    "_CP_COREX_DDM_1",
    "_CP_COREX_DDM_2",
    "_CP_COREX_DDM_3",
    "_CP_LIVR_LECT_JOYEUXD_",
    "EAD_CP_LIVR_LECT_RONDE_",
]
# --------------------------------------------------------------

def wait_loading_gone(driver, timeout=20):
    """
    Attend la disparition des overlays/spinners typiques.
    - Texte 'Chargement en cours'
    - Classes fréquentes d’overlay
    - jQuery.active == 0 si jQuery est présent
    """
    def _ready(d):
        # 1) plus de texte 'Chargement en cours'
        if d.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'Chargement en cours')]"):
            # visible ?
            for el in d.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'Chargement en cours')]"):
                if el.is_displayed():
                    return False
        # 2) plus d’overlays visibles courants
        selectors = [
            ".blockUI", ".ui-blockui", ".k-loading-mask", ".loading",
            ".spinner", ".overlay", "[aria-busy='true']"
        ]
        for sel in selectors:
            try:
                for el in d.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        return False
            except Exception:
                pass
        # 3) si jQuery présent : plus de requêtes actives
        try:
            jq = d.execute_script("return !!window.jQuery && jQuery.active")
            if jq:  # > 0
                return False
        except Exception:
            pass
        return True

    WebDriverWait(driver, timeout, poll_frequency=0.2).until(_ready)

def screenshot_bytes(driver) -> bytes:
    buf = io.BytesIO()
    buf.write(driver.get_screenshot_as_png())
    return buf.getvalue()

def se_connecter(driver, login_url: str, identifiant: str, motdepasse: str, log):
    driver.get(login_url)
    wait = WebDriverWait(driver, 20)
    champ_login = wait.until(EC.visibility_of_element_located((By.ID, "Login")))
    champ_pass  = wait.until(EC.visibility_of_element_located((By.ID, "Pass")))
    champ_login.clear(); champ_login.send_keys(identifiant)
    champ_pass.clear();  champ_pass.send_keys(motdepasse)

    bouton_submit = wait.until(EC.element_to_be_clickable((
        By.XPATH, "//input[@type='submit' and contains(translate(@value,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'se connecter')]"
    )))
    bouton_submit.click()

    try:
        wait.until(EC.any_of(
            EC.url_changes(login_url),
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='logout'], [data-testid='account-menu'], .account"))
        ))
        log("✅ Connexion réussie.")
    except Exception:
        log("⚠️ Connexion non confirmée — vérifie identifiants/sélecteurs.")

def cliquer_bouton_ok(driver, log):
    wait = WebDriverWait(driver, 10)
    try:
        bouton_ok = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='button' and @value='OK']")))
        driver.execute_script("arguments[0].click();", bouton_ok)
        log("✅ Popup 'OK' cliquée.")
    except Exception:
        log("ℹ️ Pas de popup 'OK' (ou déjà fermée).")

def rechercher_article(driver, base_url: str, texte: str, log):
    wait = WebDriverWait(driver, 20)
    driver.get(base_url)
    try:
        champ_recherche = wait.until(EC.visibility_of_element_located((By.NAME, "q")))
        champ_recherche.clear()
        champ_recherche.send_keys(texte)
        champ_recherche.send_keys(Keys.ENTER)
        wait.until(EC.url_contains("/Recherche"))
        log(f"🔍 Recherche envoyée : **{texte}**")
    except Exception as e:
        log(f"⚠️ Erreur pendant la recherche : {e}")

def cliquer_premier_article(driver, log):
    wait = WebDriverWait(driver, 20)
    try:
        lien_article = wait.until(EC.element_to_be_clickable((
            By.XPATH, "(//td[contains(@class,'Recherche_Reference')]//a[not(@rel)])[1]"
        )))
        nom = lien_article.text.strip()
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", lien_article)
        driver.execute_script("arguments[0].click();", lien_article)  # click JS pour éviter overlays
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
        log(f"📄 Fiche produit ouverte : **{nom}**")
    except Exception as e:
        log(f"⚠️ Impossible de cliquer sur le lien du premier article : {e}")

def ajouter_au_panier(driver, log):
    wait = WebDriverWait(driver, 20)
    btn = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "//div[contains(@class,'BoutonAjouter')]//input[@type='button' and "
        "(normalize-space(@value)='Ajouter au panier' or contains(translate(@value,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ajouter au panier'))]"
    )))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    driver.execute_script("arguments[0].click();", btn)
    log("🛒 Clic 'Ajouter au panier'.")

def confirmer_ajout_panier(driver, log):
    wait = WebDriverWait(driver, 30)
    # Si besoin : wait.until(EC.visibility_of_element_located((By.ID, "PanierConfirmation")))
    bouton_confirmer = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "#ActionsArticles input[type='button'][value=\"Confirmer l'ajout au panier\"]"
    )))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", bouton_confirmer)
    driver.execute_script("arguments[0].click();", bouton_confirmer)
    log("✅ Panier confirmé.")

def rester_sur_la_page(driver, log):
    wait = WebDriverWait(driver, 30)
    bouton_rester = wait.until(EC.element_to_be_clickable((
        By.XPATH, "//a[contains(@href,'FermerPopUp') and (normalize-space(text())='Rester sur la page' or contains(text(),'Rester sur la page'))]"
    )))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", bouton_rester)
    driver.execute_script("arguments[0].click();", bouton_rester)
    log("↩️ Bouton 'Rester sur la page' cliqué.")


# ------------------- STREAMLIT UI -------------------
st.set_page_config(page_title="Automation 3MA", layout="centered")
st.title("🧭 Remplir les paramètres et lancer l'automatisation")

warnings.filterwarnings("ignore", category=DeprecationWarning)

with st.form("cfg"):
    col1, col2 = st.columns(2)
    with col1:
        login_url = st.text_input("URL de connexion", LOGIN_URL_DEF)
        base_url  = st.text_input("URL de base (recherche)", BASE_URL_DEF)
        headless  = st.checkbox("Exécuter en headless (recommandé)", value=True)
    with col2:
        identifiant = st.text_input("Identifiant/Login", "EAD")
        motdepasse  = st.text_input("Mot de passe", "Ecole2025", type="password")

    articles_text = st.text_area(
        "Articles (un par ligne)",
        value="\n".join(ARTICLES_DEF),
        height=240
    )

    lancer = st.form_submit_button("Lancer l'automatisation")

log_box = st.empty()
def log(msg: str):
    log_box.markdown(msg)

shots = st.container()

if lancer:
    lst_articles: List[str] = [l.strip() for l in articles_text.splitlines() if l.strip()]
    driver = make_driver(headless=headless)
    try:
        st.info("Démarrage…")
        se_connecter(driver, login_url, identifiant, motdepasse, log)
        shots.image(screenshot_bytes(driver), caption="Après login", use_container_width=True)

        cliquer_bouton_ok(driver, log)
        shots.image(screenshot_bytes(driver), caption="Après popup OK (si présente)", use_container_width=True)

        for article in lst_articles:
            log(f"### ➤ Ajout de l'article : **{article}**")
            rechercher_article(driver, base_url, article, log)
            shots.image(screenshot_bytes(driver), caption=f"Résultats pour {article}", use_container_width=True)

            cliquer_premier_article(driver, log)
            shots.image(screenshot_bytes(driver), caption="Fiche produit", use_container_width=True)

            ajouter_au_panier(driver, log)
            confirmer_ajout_panier(driver, log)
            shots.image(screenshot_bytes(driver), caption="Popup de confirmation", use_container_width=True)

            rester_sur_la_page(driver, log)
            shots.image(screenshot_bytes(driver), caption="Retour page (après confirmation)", use_container_width=True)

        st.success("Flux terminé ✅")
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        try:
            shots.image(screenshot_bytes(driver), caption="Capture au moment de l'erreur", use_container_width=True)
        except Exception:
            pass
    finally:
        # En app Streamlit on ferme le driver à la fin (pas de boucle infinie)
        try:
            driver.quit()
        except Exception:
            pass
