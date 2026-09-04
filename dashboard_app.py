"""
Fichier : dashboard_app.py
Description : Interface décisionnelle Streamlit connectée à la couche Gold.
              Affiche les KPIs e-commerce et les alertes prédictives de stock.

"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration de la page Streamlit
st.set_page_config(page_title="E-Commerce Stock Optimizer", layout="wide", page_icon="📦")

# Chemins des données
GOLD_PARQUET = "data/gold/gold_fact_daily_demand.parquet"
PREDICTIONS_PARQUET = "data/gold/predictions_demand_j7.parquet"

# Chargement sécurisé des données
@st.cache_data
def load_data():
    if os.path.exists(GOLD_PARQUET):
        df_hist = pd.read_parquet(GOLD_PARQUET)
        df_hist['date_reference'] = pd.to_datetime(df_hist['date_reference'])
    else:
        df_hist = pd.DataFrame()
        
    if os.path.exists(PREDICTIONS_PARQUET):
        df_pred = pd.read_parquet(PREDICTIONS_PARQUET)
        df_pred['date_reference'] = pd.to_datetime(df_pred['date_reference'])
    else:
        df_pred = pd.DataFrame()
        
    return df_hist, df_pred

df_hist, df_pred = load_data()

# --- EN-TÊTE DU DASHBOARD ---
st.title("📦 Plateforme Décisionnelle d'Optimisation des Stocks")
st.markdown("**Pilote Analytique et Prédictif connecté à la Couche Gold (DuckDB & Parquet)** — *École Polytechnique de Thiès*")
st.write("---")

if df_hist.empty:
    st.error("Erreur : La table de données historiques Gold est introuvable. Veuillez exécuter le pipeline au préalable.")
else:
    # --- SECTION 1 : LES METRIQUES CLES (KPIs) ---
    st.subheader("📊 Performance Opérationnelle Globale (30 Derniers Jours)")
    
    total_ca = df_hist['chiffre_affaires'].sum()
    total_ventes = df_hist['quantite_vendue_totale'].sum()
    total_clics = df_hist['total_visites'].sum()
    taux_conversion = (df_hist['total_ajouts_panier'].sum() / total_clics * 100) if total_clics > 0 else 0
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(label="Chiffre d'Affaires Cumulé", value=f"{total_ca:,.2f} €")
    kpi2.metric(label="Unités Totales Vendues", value=f"{total_ventes:,} pcs")
    kpi3.metric(label="Trafic Web (Visites)", value=f"{total_clics:,} clics")
    kpi4.metric(label="Taux d'Ajout au Panier", value=f"{taux_conversion:.2f} %")
    
    st.write("---")
    
    # --- SECTION 2 : ANALYSE DES COMPORTEMENTS & DES VENTES ---
    col_gauche, col_droite = st.columns(2)
    
    with col_gauche:
        st.subheader("📈 Évolution Temporelle des Ventes et du CA")
        df_daily_revenue = df_hist.groupby('date_reference')['chiffre_affaires'].sum().reset_index()
        fig_line = px.line(df_daily_revenue, x='date_reference', y='chiffre_affaires', 
                           labels={'chiffre_affaires': 'Revenus (€)', 'date_reference': 'Date'},
                           color_discrete_sequence=['#1f77b4'])
        st.plotly_chart(fig_line, use_container_width=True)
        
    with col_droite:
        st.subheader("Parts du CA par Catégorie de Produits")
        df_cat = df_hist.groupby('category')['chiffre_affaires'].sum().reset_index()
        fig_pie = px.pie(df_cat, values='chiffre_affaires', names='category', 
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    st.write("---")
    
    # --- SECTION 3 : CONSOLE PRÉDICTIVE (MACHINE LEARNING) ---
    st.header("🔮 Planification Prédictive des Stocks (Alerte Approvisionnement J+7)")
    
    if df_pred.empty:
        st.warning("⚠️ Aucune donnée prédictive trouvée. Veuillez exécuter le script `demand_forecasting.py` pour générer les prévisions.")
    else:
        # Filtre interactif par catégorie pour les gestionnaires de stocks
        liste_categories = ["Toutes"] + list(df_pred['category'].unique())
        cat_choisie = st.selectbox("Filtrer les prévisions par catégorie de produit :", liste_categories)
        
        df_pred_filtered = df_pred if cat_choisie == "Toutes" else df_pred[df_pred['category'] == cat_choisie]
        
        # Graphique des prévisions de demande cumulées par jour futur
        df_future_trend = df_pred_filtered.groupby('date_reference')['demande_predite'].sum().reset_index()
        fig_pred_line = px.bar(df_future_trend, x='date_reference', y='demande_predite',
                               title=f"Volume global de la demande estimée - Catégorie : {cat_choisie}",
                               labels={'demande_predite': 'Unités à Prévoir', 'date_reference': 'Date Future'},
                               color_discrete_sequence=['#ff7f0e'])
        st.plotly_chart(fig_pred_line, use_container_width=True)
        
        # Tableau récapitulatif des achats de stocks recommandés pour la semaine suivante
        st.subheader("📋 Matrice de Commande Fournisseur Recommandée")
        
        df_summary_orders = df_pred_filtered.groupby(['product_id', 'product_name', 'category', 'unit_price']).agg({
            'demande_predite': 'sum',
            'stock_securite_recommande': 'sum'
        }).reset_index()
        
        df_summary_orders.columns = [
            "Code Article", "Nom du Produit", "Catégorie", "Prix Unitaire (€)", 
            "Demande Totale Estimée (7j)", "Stock Cible Recommandé (Inclus Marge Sécurité)"
        ]
        
        # Style visuel pour le tableau de décision
        st.dataframe(df_summary_orders.style.background_gradient(subset=["Stock Cible Recommandé (Inclus Marge Sécurité)"], cmap="Oranges"), 
                     use_container_width=True)

# Pied de page
st.write("---")
st.caption("Plateforme opérationnelle développée dans le cadre du Master Data Engineering - EPT - Juillet 2026.")