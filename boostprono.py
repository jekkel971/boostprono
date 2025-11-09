# app.py
import streamlit as st
import json
import os
import shutil
from datetime import datetime
import pandas as pd
import numpy as np

# ---------------- CONFIG ----------------
st.set_page_config(page_title="BoostProno amélioré", layout="wide")

TEAMS_FILE = "teams_form.json"
HIST_FILE = "historique_pronos.json"
BACKUP_TEAMS_DIR = "sauvegardes_teams"
BACKUP_HIST_DIR = "sauvegardes_histo"
os.makedirs(BACKUP_TEAMS_DIR, exist_ok=True)
os.makedirs(BACKUP_HIST_DIR, exist_ok=True)

# ---------------- utilitaires ----------------
def safe_load_json(path, expected_type):
    """Charge un json en forçant type de retour (list ou dict). Si invalide, retourne vide du type."""
    if not os.path.exists(path):
        return expected_type()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, expected_type):
                return expected_type()
            return data
    except Exception:
        return expected_type()

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def backup(path, dest_dir):
    if os.path.exists(path):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = os.path.basename(path).replace(".json","")
        dest = os.path.join(dest_dir, f"{base}_{ts}.json")
        shutil.copy(path, dest)

# ---------------- chargement ----------------
teams = safe_load_json(TEAMS_FILE, dict)
history = safe_load_json(HIST_FILE, list)

# backup at startup (keeps previous versions)
backup(TEAMS_FILE, BACKUP_TEAMS_DIR)
backup(HIST_FILE, BACKUP_HIST_DIR)

# ---------------- sidebar: backups & actions ----------------
st.sidebar.header("⎔ Sauvegardes & actions")
if st.sidebar.button("🔁 Sauvegarder équipes (manuel)"):
    save_json(TEAMS_FILE, teams)
    backup(TEAMS_FILE, BACKUP_TEAMS_DIR)
    st.sidebar.success("Équipes sauvegardées")

if st.sidebar.button("🔁 Sauvegarder historique (manuel)"):
    save_json(HIST_FILE, history)
    backup(HIST_FILE, BACKUP_HIST_DIR)
    st.sidebar.success("Historique sauvegardé")

if st.sidebar.button("🧹 Forcer rebuild historique vide"):
    history = []
    save_json(HIST_FILE, history)
    st.sidebar.warning("Historique réinitialisé (forcé).")

st.title("⚽ BoostProno — version améliorée")

# ---------------- Section : équipes ----------------
st.header("1) Gestion des équipes (forme & stats)")
with st.form("team_form", clear_on_submit=True):
    tname = st.text_input("Nom équipe (ex: PSG)")
    last5 = st.text_input("5 derniers (ordre récent→ancien) ex: v,n,d,v,d")
    goals_scored = st.number_input("Buts marqués (total saison)", min_value=0, value=0, step=1)
    goals_against = st.number_input("Buts encaissés (total saison)", min_value=0, value=0, step=1)
    submit_team = st.form_submit_button("Enregistrer équipe")
if submit_team:
    if not tname:
        st.error("Donne un nom d'équipe.")
    else:
        teams[tname] = {
            "last5": last5.lower(),
            "goals_scored": int(goals_scored),
            "goals_against": int(goals_against)
        }
        save_json(TEAMS_FILE, teams)
        backup(TEAMS_FILE, BACKUP_TEAMS_DIR)
        st.success(f"Équipe '{tname}' enregistrée.")

if teams:
    st.subheader("Équipes enregistrées")
    st.table(pd.DataFrame.from_dict(teams, orient="index").reset_index().rename(columns={"index":"team"}))
else:
    st.info("Aucune équipe enregistrée pour l'instant.")

st.markdown("---")

# ---------------- Section : création pronostic ----------------
st.header("2) Créer & enregistrer un pronostic (mise fixe 10€)")
if not teams:
    st.warning("Ajoute d'abord des équipes.")
else:
    colA, colB = st.columns(2)
    with colA:
        home = st.selectbox("Équipe domicile", list(teams.keys()))
    with colB:
        away_options = [t for t in teams.keys() if t != home]
        away = st.selectbox("Équipe extérieur", away_options)

    c_home = st.number_input("Cote domicile", min_value=1.01, value=1.5, step=0.01)
    c_draw = st.number_input("Cote nul (optionnel)", min_value=1.01, value=3.5, step=0.01)
    c_away = st.number_input("Cote extérieur", min_value=1.01, value=4.0, step=0.01)

    # Algorithme amélioré : cotes implicites + facteurs dynamiques
    def compute_probabilities(home, away, c_home, c_draw, c_away):
        # prob implicite depuis cotes
        ph = 1.0 / c_home
        pd = 1.0 / c_draw
        pa = 1.0 / c_away

        # normalisation base
        base_total = ph + pd + pa
        ph /= base_total
        pd /= base_total
        pa /= base_total

        # forme (score 0..1)
        def form_score(s):
            if not s: return 0.5
            parts = [x.strip().lower() for x in s.split(",") if x.strip()]
            mapping = {"v":1.0, "n":0.5, "d":0.0}
            vals = [mapping.get(p,0.5) for p in parts[:5]]  # recent->older
            # pondération recent→older
            weights = np.array([5,4,3,2,1])[:len(vals)]
            score = np.dot(vals, weights) / weights.sum()
            return float(score)  # 0..1

        fh = form_score(teams[home].get("last5",""))
        fa = form_score(teams[away].get("last5",""))

        # différence de buts (normalisée)
        gh = teams[home].get("goals_scored",0)
        gha = teams[home].get("goals_against",0)
        ga = teams[away].get("goals_scored",0)
        gaa = teams[away].get("goals_against",0)
        gd_home = (gh - gha) / max(1, gh+gha)  # approx -1..1
        gd_away = (ga - gaa) / max(1, ga+gaa)

        # avantage domicile factor
        home_adv = 0.08  # base 8% advantage

        # dynamic weighting: if odds are very divergent, trust odds more.
        # compute odds disparity:
        odds_ratio = max(c_home, c_away) / min(c_home, c_away)
        # map ratio to weight for odds in [0.6..0.9] (larger disparity -> higher weight)
        odds_weight = float(np.clip(0.6 + (odds_ratio - 1) * 0.15, 0.6, 0.9))
        form_weight = 1 - odds_weight

        # compute adjustments from form & goal diff
        # scale factors into range roughly [-0.15, +0.15]
        adjust_h = ( (fh - fa) * 0.6 + (gd_home - gd_away) * 0.4 ) * 0.15
        adjust_a = ( (fa - fh) * 0.6 + (gd_away - gd_home) * 0.4 ) * 0.15

        # assemble probabilities: base from odds, adjusted by form/goal diff and home advantage
        ph_adj = ph * odds_weight + (fh * form_weight) * (1 - odds_weight)
        pa_adj = pa * odds_weight + (fa * form_weight) * (1 - odds_weight)
        pd_adj = pd  # keep draw from odds primarily

        # apply small adjustments
        ph_adj = ph_adj * (1 + adjust_h + home_adv)
        pa_adj = pa_adj * (1 + adjust_a)
        pd_adj = pd_adj  # no form adjust for draw

        # final normalize
        total = ph_adj + pd_adj + pa_adj
        ph_final = ph_adj / total
        pd_final = pd_adj / total
        pa_final = pa_adj / total

        return {"home": ph_final, "draw": pd_final, "away": pa_final,
                "weights": {"odds_weight": odds_weight, "form_weight": form_weight},
                "form": {"fh": fh, "fa": fa},
                "gd": {"gd_home": gd_home, "gd_away": gd_away}}

    probs_info = compute_probabilities(home, away, c_home, c_draw, c_away)

    if st.button("Analyser & Enregistrer"):
        p_home = probs_info["home"]
        p_draw = probs_info["draw"]
        p_away = probs_info["away"]

        # choose winner (max prob)
        if p_home >= max(p_draw, p_away):
            winner_pred = "home"
            winner_name = home
        elif p_away >= max(p_home, p_draw):
            winner_pred = "away"
            winner_name = away
        else:
            winner_pred = "draw"
            winner_name = "Nul"

        record = {
            "ts": datetime.utcnow().isoformat(),
            "home": home,
            "away": away,
            "cote_home": float(c_home),
            "cote_draw": float(c_draw),
            "cote_away": float(c_away),
            "p_home": float(round(p_home,4)),
            "p_draw": float(round(p_draw,4)),
            "p_away": float(round(p_away,4)),
            "winner_pred": winner_pred,
            "winner_name": winner_name,
            "mise": 10.0,
            "result": None,
            "gain": None
        }
        history.append(record)
        save_json(HIST_FILE, history)
        backup(HIST_FILE, BACKUP_HIST_DIR)
        st.success(f"Pronostic enregistré → {winner_name} ({max(p_home,p_draw,p_away)*100:.1f}%)")

    # show details
    st.subheader("Probabilités calculées")
    st.write(f"🏠 {home} : {probs_info['home']*100:.2f}%")
    st.write(f"🤝 Nul : {probs_info['draw']*100:.2f}%")
    st.write(f"🚗 {away} : {probs_info['away']*100:.2f}%")
    st.write("— Pondérations dynamiques :", probs_info["weights"])
    st.write("— Formes (0..1) :", probs_info["form"])
    st.write("— Goal diffs approx :", probs_info["gd"])

st.markdown("---")

# ---------------- Section : suivi & mise à jour manuelle (nom d'équipe visible) ----------------
st.header("3) Suivi des pronostics & mise à jour des résultats (manuel)")

if not history:
    st.info("Aucun pronostic enregistré.")
else:
    # build display list "index - Home vs Away - date"
    display_list = []
    for idx, rec in enumerate(history):
        ts = rec.get("ts", "")
        display = f"{idx+1} - {rec['home']} vs {rec['away']} — {ts} — préd: {rec['winner_name']}"
        display_list.append(display)

    sel = st.selectbox("Choisir un pronostic à mettre à jour", options=display_list, key="sel_prono")
    sel_idx = display_list.index(sel)

    # show current record
    rec = history[sel_idx]
    st.write("Pronostic sélectionné :")
    st.write(pd.DataFrame([rec]).T.rename(columns={0:"value"}))

    # choose result with readable labels
    res_map = {"home": rec["home"], "draw": "Nul", "away": rec["away"]}
    choice = st.radio("Résultat réel :", options=[res_map["home"], res_map["draw"], res_map["away"]], index=0)

    if st.button("Enregistrer résultat réel"):
        # map back to key
        if choice == res_map["home"]:
            real_key = "home"
        elif choice == res_map["away"]:
            real_key = "away"
        else:
            real_key = "draw"

        # compute gain
        mise = rec.get("mise", 10.0)
        if real_key == "home":
            win = rec["winner_pred"] == "home"
            odds = rec["cote_home"]
        elif real_key == "away":
            win = rec["winner_pred"] == "away"
            odds = rec["cote_away"]
        else:
            win = rec["winner_pred"] == "draw"
            odds = rec["cote_draw"]

        if win:
            gain = round(mise * (odds - 1), 2)
        else:
            gain = -round(mise, 2)

        # update record
        history[sel_idx]["result"] = real_key
        history[sel_idx]["gain"] = gain
        history[sel_idx]["real_name"] = choice
        history[sel_idx]["correct"] = bool(win)
        save_json(HIST_FILE, history)
        backup(HIST_FILE, BACKUP_HIST_DIR)
        st.success(f"Résultat enregistré — correct: {win} — gain: {gain}€")

    st.markdown("---")
    # summary stats for validated pronos
    df_hist = pd.DataFrame(history)
    df_done = df_hist[df_hist["result"].notna()].copy()
    if not df_done.empty:
        total = len(df_done)
        correct = int(df_done["correct"].sum())
        accuracy = correct / total * 100
        total_gain = df_done["gain"].sum()
        roi = (total_gain / (total * 10.0)) * 100  # fixed stake 10€

        st.subheader("Performances globales")
        st.metric("Pronostics finalisés", total)
        st.metric("Précision", f"{accuracy:.2f}%")
        st.metric("Gain total", f"{total_gain:.2f} €")
        st.metric("ROI", f"{roi:.2f}%")

        # breakdown by type (home/draw/away)
        st.subheader("Fiabilité par type de pari")
        breakdown = []
        for key,label in [("home","Domicile"),("draw","Nul"),("away","Extérieur")]:
            subset = df_done[df_done["winner_pred"] == key]
            if len(subset)==0:
                acc = None
            else:
                acc = subset["correct"].sum() / len(subset) * 100
            breakdown.append({"type": label, "count": len(subset), "accuracy": None if acc is None else round(acc,2)})
        st.table(pd.DataFrame(breakdown))

        # top teams by correct predictions
        st.subheader("Top équipes (pronos corrects)")
        team_stats = {}
        for _, r in df_done.iterrows():
            for side in ("home","away"):
                team = r[side]
                team_stats.setdefault(team, {"played":0,"correct":0,"gain":0.0})
                team_stats[team]["played"] += 1
                if r.get("correct"):
                    team_stats[team]["correct"] += 1
                team_stats[team]["gain"] += float(r.get("gain") or 0.0)
        if team_stats:
            df_team = pd.DataFrame([
                {"team": k, "played": v["played"], "correct": v["correct"],
                 "accuracy (%)": round(v["correct"]/v["played"]*100,2),
                 "gain (€)": round(v["gain"],2)}
                for k,v in team_stats.items()
            ]).sort_values("accuracy (%)", ascending=False)
            st.dataframe(df_team, use_container_width=True)

    # export and reset
    st.download_button("Télécharger historique (CSV)", df_hist.to_csv(index=False).encode("utf-8"), "historique.csv")
    if st.button("Réinitialiser historique (supprime tout)"):
        history = []
        save_json(HIST_FILE, history)
        backup(HIST_FILE, BACKUP_HIST_DIR)
        st.warning("Historique supprimé.")
