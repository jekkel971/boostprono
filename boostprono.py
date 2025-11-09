import streamlit as st
import pandas as pd
import numpy as np
import json
import os

st.set_page_config(page_title="BoostProno", layout="wide")
st.title("⚽ BoostProno – Analyse de matchs et suivi de pronostics")

# ====== Fichiers de sauvegarde ======
TEAMS_FILE = "teams_data.json"
HISTO_FILE = "historique_pronos.json"

# Charger ou initialiser les données
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    teams_data = {}

if os.path.exists(HISTO_FILE):
    with open(HISTO_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# Fonctions pour sauvegarder
def save_teams():
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)

def save_historique():
    with open(HISTO_FILE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)

# ====== GESTION DES ÉQUIPES ======
st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    form_last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 1000, 0)
    goals_against = st.number_input("Buts encaissés", 0, 1000, 0)
    submitted = st.form_submit_button("💾 Enregistrer l'équipe")

if submitted and team_name:
    teams_data[team_name] = {
        "last5": form_last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    save_teams()
    st.success(f"✅ {team_name} enregistrée avec succès")

# ====== AJOUT DE PRONOSTICS ======
st.header("📊 Ajouter un pronostic")

if teams_data:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team])

    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.8)

    if st.button("➕ Ajouter le pronostic"):
        # Calcul probabilités
        def form_score(seq):
            mapping = {"v":3,"n":1,"d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals)>5 else vals
            weights = np.array([5,4,3,2,1])[:len(vals)]
            return np.dot(vals, weights) / (15 if len(vals)==5 else sum(weights))

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        # Cotes en probabilité
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away

        # Fusion forme + cotes
        prob_home = 0.7*p_home_odds + 0.3*form_home
        prob_away = 0.7*p_away_odds + 0.3*form_away
        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total

        winner = home_team if prob_home > prob_away else away_team
        prob_victoire = round(max(prob_home, prob_away)*100,2)

        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": prob_victoire,
            "mise": 10,
            "resultat": None,
            "gain": 0,
            "score_home": None,
            "score_away": None
        }

        historique.append(pronostic)
        save_historique()
        st.success(f"✅ Pronostic ajouté : victoire de {winner} ({prob_victoire}%)")

else:
    st.warning("⚠️ Ajoute d'abord des équipes.")

# ====== MISE À JOUR DES RESULTATS ======
st.header("📅 Suivi des résultats")

if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]], use_container_width=True)

    st.subheader("📝 Mettre à jour un match")
    match_index = st.selectbox(
        "Sélectionner un match",
        range(len(historique)),
        format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}"
    )
    home_score = st.number_input("Buts Domicile", 0, 20, 0)
    away_score = st.number_input("Buts Extérieur", 0, 20, 0)
    if st.button("✅ Enregistrer le résultat réel"):
        prono = historique[match_index]
        # Calcul résultat
        if home_score > away_score:
            resultat = "home"
        elif home_score < away_score:
            resultat = "away"
        else:
            resultat = "draw"

        cote = prono["cote_home"] if prono["winner_pred"]==prono["home_team"] else prono["cote_away"]
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        elif resultat=="draw":
            gain = 0
        else:
            gain = -prono["mise"]

        prono["resultat"] = resultat
        prono["gain"] = gain
        prono["score_home"] = home_score
        prono["score_away"] = away_score

        # MAJ buts marqués/encaissés
        home = prono["home_team"]
        away = prono["away_team"]
        teams_data[home]["goals_scored"] += home_score
        teams_data[home]["goals_against"] += away_score
        teams_data[away]["goals_scored"] += away_score
        teams_data[away]["goals_against"] += home_score

        # MAJ forme
        def update_form(prono):
            home = prono["home_team"]
            away = prono["away_team"]
            last5_home = teams_data[home]["last5"].split(",")[:4]
            last5_away = teams_data[away]["last5"].split(",")[:4]

            if resultat=="home":
                last5_home = ["v"] + last5_home
                last5_away = ["d"] + last5_away
            elif resultat=="away":
                last5_home = ["d"] + last5_home
                last5_away = ["v"] + last5_away
            else:
                last5_home = ["n"] + last5_home
                last5_away = ["n"] + last5_away

            teams_data[home]["last5"] = ",".join(last5_home)
            teams_data[away]["last5"] = ",".join(last5_away)

        update_form(prono)
        save_teams()
        save_historique()
        st.success(f"Résultat enregistré ✅ ({home_score}-{away_score}, gain : {gain}€)")

    # Suppression ou réinitialisation
    st.subheader("🗑️ Gérer l’historique")
    if st.button("🗑️ Supprimer ce match"):
        del historique[match_index]
        save_historique()
        st.success("Match supprimé (la forme reste inchangée)")

    if st.button("♻️ Réinitialiser l'application"):
        historique.clear()
        teams_data.clear()
        save_historique()
        save_teams()
        st.warning("Application réinitialisée. Toutes les équipes et pronostics supprimés.")

    # Statistiques
    df_valides = pd.DataFrame([m for m in historique if m["resultat"] is not None])
    if not df_valides.empty:
        total_gain = df_valides["gain"].sum()
        nb_pronos = len(df_valides)
        nb_gagnants = (df_valides["gain"]>0).sum()
        precision = nb_gagnants/nb_pronos*100
        roi = total_gain/(nb_pronos*10)*100
        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")
else:
    st.info("Aucun pronostic enregistré pour le moment.")
