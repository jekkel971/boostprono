import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="BoostProno (stable)", layout="wide")

TEAMS_FILE = "teams_form.json"
HIST_FILE = "historique_pronos.json"

# ---------------- UTIL ----------------
def ensure_team_fields(team_name):
    """S'assure que l'équipe a toutes les clefs requises."""
    changed = False
    if team_name not in teams_data:
        teams_data[team_name] = {}
        changed = True
    t = teams_data[team_name]
    if "last5" not in t or not isinstance(t["last5"], str):
        t["last5"] = "v,v,n,d,d"
        changed = True
    if "goals_scored" not in t:
        t["goals_scored"] = 0
        changed = True
    if "goals_against" not in t:
        t["goals_against"] = 0
        changed = True
    if "points" not in t:
        t["points"] = 0
        changed = True
    return changed

def save_teams():
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)

def save_history():
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)

def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    else:
        return default

def form_score(seq):
    mapping = {"v":3,"n":1,"d":0}
    vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
    vals = vals[-5:] if len(vals) > 5 else vals
    weights = np.array([5,4,3,2,1])[:len(vals)]
    if len(weights)==0:
        return 0.0
    return np.dot(vals, weights)/sum(weights)

# ---------------- CHARGEMENT ----------------
teams_data = load_json_file(TEAMS_FILE, {})
historique = load_json_file(HIST_FILE, [])

# ensure fields for all known teams (avoid KeyError)
for tn in list(teams_data.keys()):
    ensure_team_fields(tn)
# also ensure teams referenced in history exist
for h in historique:
    for tn in [h.get("home_team"), h.get("away_team")]:
        if tn:
            ensure_team_fields(tn)

# Save if we added fields
save_teams()
save_history()

# ---------------- UI SIDEBAR (sauvegarde/import + gestion équipes) ----------------
st.sidebar.title("💾 Sauvegarde & Équipes")

# Export buttons
if st.sidebar.button("📥 Télécharger teams_form.json"):
    if os.path.exists(TEAMS_FILE):
        with open(TEAMS_FILE, "r", encoding="utf-8") as f:
            st.sidebar.download_button("Télécharger teams_form.json", f.read(), file_name="teams_form.json")
    else:
        st.sidebar.warning("Aucun fichier teams_form.json trouvé.")

if st.sidebar.button("📥 Télécharger historique_pronos.json"):
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r", encoding="utf-8") as f:
            st.sidebar.download_button("Télécharger historique_pronos.json", f.read(), file_name="historique_pronos.json")
    else:
        st.sidebar.warning("Aucun fichier historique_pronos.json trouvé.")

# Import (restore) buttons
st.sidebar.markdown("---")
st.sidebar.write("📤 **Restaurer / importer** (uploader un JSON pour remplacer)")
uploaded_teams = st.sidebar.file_uploader("Importer teams_form.json", type="json")
if uploaded_teams is not None:
    try:
        data = json.load(uploaded_teams)
        if isinstance(data, dict):
            # write file and reload
            with open(TEAMS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            st.sidebar.success("teams_form.json importé. Recharge la page principale.")
            st.experimental_rerun()
        else:
            st.sidebar.error("Fichier invalide (doit être un objet JSON/dict).")
    except Exception as e:
        st.sidebar.error(f"Erreur import teams: {e}")

uploaded_hist = st.sidebar.file_uploader("Importer historique_pronos.json", type="json")
if uploaded_hist is not None:
    try:
        data = json.load(uploaded_hist)
        if isinstance(data, list):
            with open(HIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            st.sidebar.success("historique_pronos.json importé. Recharge la page principale.")
            st.experimental_rerun()
        else:
            st.sidebar.error("Fichier invalide (doit être une liste JSON).")
    except Exception as e:
        st.sidebar.error(f"Erreur import historique: {e}")

st.sidebar.markdown("---")
# Add / edit team in sidebar
st.sidebar.subheader("➕ Ajouter / modifier une équipe")
with st.sidebar.form("add_team_form"):
    t_name = st.text_input("Nom de l'équipe")
    t_last5 = st.text_input("5 derniers (ex: v,v,n,d,v)", value="v,v,n,d,d")
    t_goals_scored = st.number_input("Buts marqués", 0, 200, 0, key="gs")
    t_goals_against = st.number_input("Buts encaissés", 0, 200, 0, key="ga")
    submitted_team = st.form_submit_button("Enregistrer équipe")
if submitted_team and t_name:
    teams_data[t_name] = {
        "last5": t_last5.lower(),
        "goals_scored": int(t_goals_scored),
        "goals_against": int(t_goals_against),
        "points": teams_data.get(t_name, {}).get("points", 0)
    }
    ensure_team_fields(t_name)
    save_teams()
    st.sidebar.success(f"Équipe « {t_name} » enregistrée.")

st.sidebar.markdown("---")
if st.sidebar.button("⚠️ Réinitialiser toutes les données (supprime tout)"):
    if st.sidebar.checkbox("Je confirme la réinitialisation complète", key="confirm_reset"):
        # remove files if exist
        if os.path.exists(TEAMS_FILE): os.remove(TEAMS_FILE)
        if os.path.exists(HIST_FILE): os.remove(HIST_FILE)
        teams_data.clear()
        historique.clear()
        st.sidebar.warning("Données réinitialisées — recharge la page.")
        st.experimental_rerun()

# ---------------- ENTETE PRINCIPAL ----------------
st.title("⚽ BoostProno — Stable & Sauvegardes")
st.write("Interface : gestion équipes (barre latérale), pronostics, résultats et statistiques.")

# ---------------- AJOUT PRONOSTIC ----------------
st.header("📊 Ajouter un pronostic (manuel)")
if len(teams_data) < 2:
    st.info("Ajoute au moins 2 équipes dans la barre latérale pour pouvoir créer un pronostic.")
else:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()), key="home_sel")
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team], key="away_sel")

    cote_home = st.number_input("Cote Domicile", 1.01, 30.0, 1.5, key="coteh")
    cote_away = st.number_input("Cote Extérieure", 1.01, 30.0, 2.5, key="cotea")
    # optional predicted score (keeps data)
    pred_home = st.number_input("Prédiction buts domicile (optionnel)", 0, 20, 0, key="ph")
    pred_away = st.number_input("Prédiction buts extérieur (optionnel)", 0, 20, 0, key="pa")

    if st.button("➕ Enregistrer pronostic"):
        # ensure teams fields exist
        ensure_team_fields(home_team)
        ensure_team_fields(away_team)

        fh = form_score(teams_data[home_team]["last5"])
        fa = form_score(teams_data[away_team]["last5"])
        # improved fusion: weights favor form but keep odds influence
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away
        prob_home = 0.65*fh + 0.35*p_home_odds
        prob_away = 0.65*fa + 0.35*p_away_odds
        total = prob_home + prob_away
        if total == 0:
            prob_home = prob_away = 0.5
        else:
            prob_home /= total
            prob_away /= total

        winner = home_team if prob_home > prob_away else away_team
        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": float(cote_home),
            "cote_away": float(cote_away),
            "winner_pred": winner,
            "prob_victoire": round(max(prob_home, prob_away)*100,2),
            "mise": 10,
            "resultat": None,
            "score_home": None,
            "score_away": None,
            "gain": 0,
            "pred_home": int(pred_home),
            "pred_away": int(pred_away),
            "timestamp": datetime.utcnow().isoformat()
        }
        historique.append(pronostic)
        save_history()
        st.success(f"Pronostic ajouté — {winner} ({pronostic['prob_victoire']}%).")

# ---------------- SUIVI RESULTATS ----------------
st.header("📅 Suivi des pronostics & mise à jour des résultats")
if not historique:
    st.info("Aucun pronostic enregistré pour le moment.")
else:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","score_home","score_away","gain"]], use_container_width=True)

    st.subheader("📝 Mettre à jour un match joué (saisie du score réel)")
    idx = st.selectbox("Sélectionner un match", range(len(historique)),
                       format_func=lambda i: f"{i+1} - {historique[i]['home_team']} vs {historique[i]['away_team']}")
    sel = historique[idx]
    st.markdown(f"**Match choisi :** {sel['home_team']} vs {sel['away_team']} — prédiction : {sel['winner_pred']} ({sel['prob_victoire']}%)")
    real_home = st.number_input("Buts domicile (réel)", 0, 20, 0, key=f"real_h_{idx}")
    real_away = st.number_input("Buts extérieur (réel)", 0, 20, 0, key=f"real_a_{idx}")
    if st.button("✅ Enregistrer score réel et mettre à jour équipes", key=f"save_score_{idx}"):
        # determine result
        if real_home > real_away:
            resultat_real = "home"
        elif real_home < real_away:
            resultat_real = "away"
        else:
            resultat_real = "draw"
        # compute gain
        cote = sel["cote_home"] if sel["winner_pred"] == sel["home_team"] else sel["cote_away"]
        gain = round(sel["mise"] * cote - sel["mise"], 2) if (
            (resultat_real == "home" and sel["winner_pred"] == sel["home_team"]) or
            (resultat_real == "away" and sel["winner_pred"] == sel["away_team"])
        ) else -sel["mise"]

        # update history entry
        sel["resultat"] = resultat_real
        sel["score_home"] = int(real_home)
        sel["score_away"] = int(real_away)
        sel["gain"] = float(gain)
        save_history()

        # Update teams permanently (won't roll back if match removed)
        ensure_team_fields(sel["home_team"])
        ensure_team_fields(sel["away_team"])

        def push_result(team, outcome_char, goals_for, goals_against):
            seq = teams_data[team]["last5"].split(",")[:4]
            seq = [outcome_char] + seq
            teams_data[team]["last5"] = ",".join(seq)
            teams_data[team]["goals_scored"] += int(goals_for)
            teams_data[team]["goals_against"] += int(goals_against)

        if resultat_real == "home":
            push_result(sel["home_team"], "v", real_home, real_away)
            push_result(sel["away_team"], "d", real_away, real_home)
        elif resultat_real == "away":
            push_result(sel["home_team"], "d", real_home, real_away)
            push_result(sel["away_team"], "v", real_away, real_home)
        else:
            push_result(sel["home_team"], "n", real_home, real_away)
            push_result(sel["away_team"], "n", real_away, real_home)

        save_teams()
        st.success(f"Score enregistré — résultat : {resultat_real}, gain : {gain}€")

    # ---------------- Supprimer un match spécifique ----------------
    st.subheader("🗑️ Supprimer un match (ne modifie pas les stats des équipes)")
    del_idx = st.selectbox("Choisir match à supprimer", range(len(historique)),
                           format_func=lambda i: f"{i+1} - {historique[i]['home_team']} vs {historique[i]['away_team']}", key="del_sel")
    if st.button("❌ Supprimer le match sélectionné"):
        removed = historique.pop(del_idx)
        save_history()
        st.warning(f"Match supprimé : {removed['home_team']} vs {removed['away_team']} (les stats équipes restent inchangées)")

    # ---------------- Statistiques ----------------
    st.subheader("📈 Statistiques")
    df_all = pd.DataFrame(historique)
    df_done = df_all[df_all["resultat"].notna()] if not df_all.empty else pd.DataFrame()
    if not df_done.empty:
        total_gain = df_done["gain"].sum()
        nb = len(df_done)
        nb_won = (df_done["gain"] > 0).sum()
        precision = nb_won/nb * 100
        roi = (total_gain / (nb * 10)) * 100
        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")
    else:
        st.info("Aucun match terminé pour calculer les statistiques.")

# ---------------- FIN ----------------
st.markdown("---")
st.caption("Sauvegardes : télécharge tes JSON depuis la barre latérale avant de modifier le code. Les mises à jour de scores modifient définitivement les stats des équipes.")
