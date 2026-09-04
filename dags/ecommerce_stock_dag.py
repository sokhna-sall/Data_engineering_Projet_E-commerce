"""
Fichier : ecommerce_stock_dag.py
Description : Graphe Orienté Acyclique (DAG) Airflow gérant la planification 
              quotidienne du pipeline e-commerce.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# Import des fonctions modulaires du transform_pipeline
try:
    from transform_pipeline import run_bronze_to_silver, run_data_quality_tests, run_silver_to_gold
except ImportError:
    # Sauvegarde de sécurité si les fichiers ne partagent pas le même PATH sous l'exécuteur Airflow
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from transform_pipeline import run_bronze_to_silver, run_data_quality_tests, run_silver_to_gold

# 1. Définition des paramètres généraux par défaut (Best Practices)
default_args = {
    'owner': 'Equipe_Data_Engineering_EPT',
    'depends_on_past': False,
    'start_date': datetime(2026, 6, 1),      # Aligné sur l'historique fictif des données
    'email_on_failure': True,
    'email': 'alert-data-pipeline@ept.sn',
    'retries': 2,                             # Nombre de tentatives en cas de panne temporaire
    'retry_delay': timedelta(minutes=5),     # Temps d'attente entre deux tentatives
}

# 2. Instanciation du DAG d'orchestration
with DAG(
    dag_id='dag_optimisation_stocks_ecommerce',
    default_args=default_args,
    description='Pipeline quotidien ELT de gestion et prévision des stocks du e-commerce',
    schedule_interval='0 2 * * *',           # Planification automatique chaque jour à 02h00 AM
    catchup=False,                            # Évite de rejouer tout l'historique passé à l'activation
    tags=['e-commerce', 'medallion', 'duckdb', 'gold_parquet'],
) as dag:

    # Tâche 1 : Capteur de validation de présence des fichiers sources en zone d'atterrissage
    task_check_bronze_files = BashOperator(
        task_id='verifier_fichiers_bronze_existants',
        bash_command='test -f data/bronze/catalogue_produits.csv && test -f data/bronze/historique_ventes.csv',
    )

    # Tâche 2 : Appel de la transformation de nettoyage de la couche Silver
    task_transform_silver = PythonOperator(
        task_id='executer_transformation_bronze_vers_silver',
        python_callable=run_bronze_to_silver,
    )

    # Tâche 3 : Barrière de contrôle qualité (Bloquante en cas de ValueError)
    task_validate_quality = PythonOperator(
        task_id='executer_tests_data_quality_silver',
        python_callable=run_data_quality_tests,
    )

    # Tâche 4 : Génération de la table Gold finale consolidée
    task_generate_gold = PythonOperator(
        task_id='generer_couche_gold_parquet',
        python_callable=run_silver_to_gold,
    )

    # Tâche 5 : Notification de fin de pipeline et déclenchement théorique de l'inférence ML
    task_trigger_ml = BashOperator(
        task_id='notifier_succes_et_declencher_prediction_ml',
        bash_command='echo "[Airflow Success] Couche Gold disponible. Inférence du modèle ML activée pour J+7."',
    )

    # 3. Déclaration du graphe séquentiel de dépendance
    task_check_bronze_files >> task_transform_silver >> task_validate_quality >> task_generate_gold >> task_trigger_ml