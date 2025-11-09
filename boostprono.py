import streamlit as st
import json
import os
import matplotlib.pyplot as plt
import pandas as pd
import random

# === Constantes ===
EQUIPES_FILE = "equipes.json"
HISTORIQUE_FILE = "historique_pronos.json"

# === Chargement sécurisé des fichiers ===
def charger_json(fichier, type_defaut):
    if os.path.exists(fichier):
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, type_defaut):
                    return type_defaut()
                return data
        except json.JSONDecodeError:
            return type_defaut()
    return type_defaut()

# === Sauvegarde JSON ===
def sauvegarder_json(fichier, data):
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# === Chargement des données ===
equipes = charger_json(EQUIPES_FILE, dict)
historique = charger_json(HISTORIQUE_FILE, list)

st.title("⚽ BoostProno — Analyse & Prédictions")

# === Ajout d'équipes ===
st.subheader("📝 Ajouter ou modifier une équipe")
nom_equipe = st.text_input("Nom de l'équipe")
forme = st.text_input("Forme sur les 5 derniers matchs (ex: v,n,d,v,v)").lower()

if st.button("💾 Enregistrer l'équipe"):
    if nom_equipe and forme:
        equipes[nom_equipe] = {"forme": forme}
        sauvegarder_json(EQUIPES_FILE, equipes)
        st.success(f"✅ Équipe '{nom_equipe}' enregistrée.")
    else:
        st.warning("⚠️ Veuillez remplir tous les champs.")

# === Sélection des équipes ===
st.subheader("🎯 Sélection du match à pronostiquer")
if equipes:
    col1, col2 = st.columns(2)
    with col1:
        equipe_domicile = st.selectbox("Équipe à domicile", list(equipes.keys()))
    with col2:
        equipe_exterieur = st.selectbox("Équipe à l’extérieur", list(equipes.keys()))
else:
    st.warning("Ajoutez des équipes avant de continuer.")
    st.stop()

# === Cotes ===
st.subheader("💰 Cotes du match")
col1, col2, col3 = st.columns(3)
with col1:
    cote_dom = st.number_input("Cote domicile", min_value=1.01, value=1.80)
with col2:
    cote_nul = st.number_input("Cote nul", min_value=1.01, value=3.20)
with col3:
    cote_ext = st.number_input("Cote extérieur", min_value=1.01, value=4.50)

# === Fonction de calcul de forme ===
def score_forme(forme):
    score = 0
    for match in forme:
        if match == "v":
            score += 3
        elif match == "n":
            score += 1
    return score

# === Calcul de probabilité ===
def probabilite_victoire(cote, forme_score, forme_adv):
    base = 1 / cote
    forme_facteur = 1 + (forme_score - forme_adv) / 15
    return base * forme_facteur

# === Analyse ===
if st.button("🔍 Analyser le match"):
    if equipe_domicile == equipe_exterieur:
        st.error("⚠️ Les deux équipes doivent être différentes.")
        st.stop()

    f_dom = equipes[equipe_domicile]["forme"]
    f_ext = equipes[equipe_exterieur]["forme"]

    score_dom = score_forme(f_dom)
    score_ext = score_forme(f_ext)

    p_dom = probabilite_victoire(cote_dom, score_dom, score_ext)
    p_nul = 1 / cote_nul
    p_ext = probabilite_victoire(cote_ext, score_ext, score_dom)

    total = p_dom + p_nul + p_ext
    p_dom = round((p_dom / total) * 100, 2)
    p_nul = round((p_nul / total) * 100, 2)
    p_ext = round((p_ext / total) * 100, 2)

    st.markdown(f"### 📊 Probabilités estimées :")
    st.info(f"🏠 **{equipe_domicile}** : {p_dom}%\n\n🤝 **Nul** : {p_nul}%\n\n🚗 **{equipe_exterieur}** : {p_ext}%")

    # === Résultat attendu ===
    resultat = max([(p_dom, "Domicile"), (p_nul, "Nul"), (p_ext, "Extérieur")], key=lambda x: x[0])[1]
    st.success(f"✅ Pronostic : **{resultat}**")

    # === Sauvegarde du pronostic ===
    pronostic = {
        "domicile": equipe_domicile,
        "exterieur": equipe_exterieur,
        "cote_dom": cote_dom,
        "cote_nul": cote_nul,
        "cote_ext": cote_ext,
        "p_dom": p_dom,
        "p_nul": p_nul,
        "p_ext": p_ext,
        "resultat_prevu": resultat,
        "mise": 10
    }
    historique.append(pronostic)
    sauvegarder_json(HISTORIQUE_FILE, historique)
    st.success("💾 Pronostic sauvegardé dans l’historique.")

# === Évaluation des pronostics passés ===
st.subheader("📈 Statistiques des pronostics")

if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["domicile", "exterieur", "resultat_prevu", "mise"]])

    st.markdown("### ✅ Évaluer les pronostics passés")
    index = st.number_input("Numéro du pronostic à mettre à jour", min_value=1, max_value=len(historique), step=1) - 1
    resultat_reel = st.selectbox("Résultat réel", ["Domicile", "Nul", "Extérieur"])
    if st.button("🔄 Mettre à jour le pronostic"):
        historique[index]["resultat_reel"] = resultat_reel
        historique[index]["bon_prono"] = (resultat_reel == historique[index]["resultat_prevu"])
        sauvegarder_json(HISTORIQUE_FILE, historique)
        st.success("✅ Pronostic mis à jour avec le résultat réel.")

    # Statistiques globales
    bons_pronos = [p for p in historique if p.get("bon_prono")]
    total = len(historique)
    if total > 0:
        taux_reussite = round(len(bons_pronos) / total * 100, 2)
        st.markdown(f"### 📊 Taux de réussite : **{taux_reussite}%** ({len(bons_pronos)}/{total})")

        # Graphique
        labels = ["Bons pronos", "Mauvais pronos"]
        sizes = [len(bons_pronos), total - len(bons_pronos)]
        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        st.pyplot(fig)
else:
    st.info("Aucun pronostic enregistré pour le moment.")
