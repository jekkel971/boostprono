import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

st.set_page_config(page_title="BoostProno - Analyse de matchs", layout="wide")

# --- Fichiers ---
TEAMS_FILE = "teams_form.json"
HISTO_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"

os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Sauvegarde automatique ---
def backup_file(file_path):
    if os.path.exists(file_path):
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        shutil.copy(file_path, os.path.join(BACKUP_DIR, f"{os.path.basename(file_path).replace('.json','')}_backup_{date_str}.json"))

backup_file(TEAMS_FILE)
backup_file(HISTO_FILE)

# --- Chargement équipes ---
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    teams_data = {}

# --- Chargement historique pronos ---
if os.path.exists(HISTO_FILE):
    with open(HISTO_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# ================== INTERFACE ==================
st.title("⚽ BoostProno - Analyse et suivi des pronostics")

# --- SECTION GESTION ÉQUIPES ---
st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe à ajouter ou mettre à jour")
    form_last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer l'équipe")

if submitted_team and team_name:
    teams_data[team_name] = {
        "last5": form_last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée avec succès")
    backup_file(TEAMS_FILE)

# --- SECTION AJOUT PRONOSTICS ---
st.header("📊 Ajouter un pronostic")
if teams_data:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team])

    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.8)

    if st.button("➕ Analyser & Sauvegarder le pronostic"):
        # ===== Calcul des probabilités =====
        def form_score(seq):
            mapping = {"v":3,"n":1,"d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals)>5 else vals
            weights = np.array([5,4,3,2,1][:len(vals)])
            return np.dot(vals,weights)/(15 if len(vals)==5 else sum(weights))

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        # Probabilité implicite des cotes
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away

        # Fusion forme + cotes
        prob_home = 0.6*form_home + 0.4*p_home_odds
        prob_away = 0.6*form_away + 0.4*p_away_odds
        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total

        winner = home_team if prob_home>prob_away else away_team
        prob_victoire = round(max(prob_home,prob_away)*100,2)

        mise = 10
        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": prob_victoire,
            "mise": mise,
            "resultat": None,
            "gain": 0
        }

        historique.append(pronostic)
        with open(HISTO_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success(f"✅ Pronostic enregistré : victoire de {winner} ({prob_victoire}%)")
        backup_file(HISTO_FILE)
else:
    st.warning("⚠️ Ajoute d'abord des équipes avant de pouvoir analyser un match.")

# --- SECTION SUIVI & STATISTIQUES ---
st.header("📅 Suivi des résultats & statistiques")
if historique:
    # Sécuriser les clés manquantes
    for rec in historique:
        for key in ["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]:
            if key not in rec:
                rec[key]=None if key=="resultat" else 0 if key=="gain" else "N/A"

    df = pd.DataFrame(historique)
    display_cols = [c for c in ["home_team","away_team","winner_pred","prob_victoire","resultat","gain"] if c in df.columns]
    st.dataframe(df[display_cols])

    st.subheader("📝 Mettre à jour le résultat d’un match")
    match_index = st.selectbox(
        "Sélectionne un match",
        range(len(historique)),
        format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}"
    )
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    if st.button("✅ Enregistrer résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"]==prono["home_team"] else prono["cote_away"]
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        else:
            gain = -prono["mise"]
        prono["resultat"]=resultat
        prono["gain"]=gain
        with open(HISTO_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

    # Statistiques
    df_valides = df[df["resultat"].notna()]
    if not df_valides.empty:
        total_gain = df_valides["gain"].sum()
        nb_pronos = len(df_valides)
        nb_gagnants = (df_valides["gain"]>0).sum()
        precision = nb_gagnants/nb_pronos*100
        roi = (total_gain/(nb_pronos*10))*100
        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")

    st.download_button("📥 Télécharger l’historique (CSV)",
                       df.to_csv(index=False).encode("utf-8"),
                       "historique_pronos.csv","text/csv")

    if st.button("🗑️ Réinitialiser l’historique"):
        historique.clear()
        with open(HISTO_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.warning("Historique réinitialisé")
else:
    st.info("Aucun pronostic enregistré pour le moment.")
