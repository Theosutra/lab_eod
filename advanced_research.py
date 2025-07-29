#!/usr/bin/env python3
"""
EODEN - Version Simple Ultra-Optimisée
Recherche intelligente qui retourne automatiquement la meilleure réponse
"""

import json
import time
import urllib.parse
from google.cloud import discoveryengine_v1
from google.oauth2 import service_account
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
PROJECT_ID = "eoden-465407"
DATA_STORE_ID = "eoden-store-v2_1753786474509"
LOCATION = "global"

def load_prompts_config():
    """Charge la configuration des prompts depuis le fichier JSON"""
    try:
        with open("prompts_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Erreur: Fichier prompts_config.json non trouvé")
        return None
    except json.JSONDecodeError:
        print("❌ Erreur: Format JSON invalide dans prompts_config.json")
        return None

def replace_template_variables(text, config):
    """Remplace les variables template dans le texte"""
    if not config or "template_dictionary" not in config:
        return text
    
    template_dict = config["template_dictionary"]
    result = text
    
    for key, value in template_dict.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    
    return result

def extract_document_name(uri):
    """Extrait le nom du document depuis l'URI"""
    if not uri:
        return "Document inconnu"
    
    filename = uri.split('/')[-1]
    
    if filename:
        filename = urllib.parse.unquote(filename)
        return filename
    
    return "Document sans nom"

def create_optimized_queries(base_query: str, prompt_type: str):
    """Crée 3 versions optimisées de la requête avec enrichissement contextuel"""
    
    # Synonymes enrichis par type
    synonym_mappings = {
        "CHIFFRE_AFFAIRES": {
            "chiffre d'affaires": "chiffre d'affaires revenus ventes turnover CA recettes",
            "évolution": "évolution croissance progression variation développement",
            "Reno Energy": "Reno Energy entreprise société"
        },
        "CONCURRENCE": {
            "concurrence": "concurrence concurrents compétiteurs acteurs marché rivals",
            "positionnement": "positionnement stratégie différenciation avantage",
            "marché": "marché secteur industrie segment écosystème"
        },
        "MARGE_BRUTE": {
            "marge": "marge brute profitabilité rentabilité margin profit",
            "coûts": "coûts charges dépenses frais prix revient"
        },
        "OPERATION": {
            "acquisition": "acquisition rachat investissement opération transaction deal",
            "valorisation": "valorisation valeur prix montant évaluation",
            "EODEN": "EODEN investisseur acquéreur fonds"
        },
        "PERSONNE_CLE": {
            "dirigeants": "dirigeants management équipe leadership team",
            "profil": "profil expérience parcours background"
        }
    }
    
    queries = []
    
    # Query 1: Enrichie avec synonymes + contexte prioritaire
    enriched_query = base_query
    if prompt_type in synonym_mappings:
        for term, synonyms in synonym_mappings[prompt_type].items():
            if term.lower() in enriched_query.lower():
                enriched_query = enriched_query.replace(term, synonyms)
    
    # Ajout du contexte prioritaire
    enriched_query = create_enhanced_query_with_context(enriched_query, prompt_type)
    queries.append(enriched_query)
    
    # Query 2: Précise avec mots-clés techniques prioritaires
    technical_terms = {
        "CHIFFRE_AFFAIRES": "Reno Energy chiffre affaires revenue financier EODEN 2024",
        "CONCURRENCE": "Reno Energy concurrence competitive marché secteur 2024",
        "MARGE_BRUTE": "Reno Energy marge profitabilité coûts rentabilité",
        "OPERATION": "Reno Energy acquisition EODEN transaction opération investissement 2024",
        "PERSONNE_CLE": "Reno Energy management dirigeants équipe direction"
    }
    
    technical_query = f"{base_query} {technical_terms.get(prompt_type, 'Reno Energy 2024')}"
    queries.append(technical_query)
    
    # Query 3: Courte et directe avec termes prioritaires
    short_terms = {
        "CHIFFRE_AFFAIRES": "Reno Energy chiffre affaires EODEN 2024",
        "CONCURRENCE": "Reno Energy concurrents marché 2024",
        "MARGE_BRUTE": "Reno Energy marge rentabilité",
        "OPERATION": "Reno Energy acquisition EODEN 2024",
        "PERSONNE_CLE": "Reno Energy dirigeants management"
    }
    
    short_query = short_terms.get(prompt_type, f"Reno Energy {base_query.split()[0]} 2024")
    queries.append(short_query)
    
    return queries

def create_enhanced_query_with_context(base_query: str, prompt_type: str):
    """
    Compense l'absence de boosts en enrichissant directement la requête avec des termes prioritaires
    """
    
    # Termes prioritaires à ajouter selon le type de prompt
    priority_terms = {
        "CHIFFRE_AFFAIRES": "financier chiffre affaires revenue CA 2024 2023",
        "CONCURRENCE": "marché concurrence competitive secteur 2024",
        "OPERATION": "acquisition EODEN opération transaction investissement 2024",
        "MARGE_BRUTE": "marge profitabilité rentabilité coûts",
        "PERSONNE_CLE": "management équipe dirigeants organigramme",
        "MARCHE": "marché secteur énergies renouvelables photovoltaïque",
        "PRESENTATION": "présentation profil entreprise société Reno Energy"
    }
    
    # Ajout des termes prioritaires à la requête
    enhanced_query = base_query
    if prompt_type in priority_terms:
        enhanced_query = f"{base_query} {priority_terms[prompt_type]}"
    
    # Toujours privilégier les documents récents et EODEN
    enhanced_query = f"{enhanced_query} EODEN 2024 2023"
    
    return enhanced_query

def create_optimized_request(query: str, prompt_type: str, system_prompt: str, serving_config: str):
    """Crée une requête ultra-optimisée compatible avec chunking config"""
    
    content_search_spec = discoveryengine_v1.SearchRequest.ContentSearchSpec(
        # Plus d'extraits pour plus de contexte
        snippet_spec=discoveryengine_v1.SearchRequest.ContentSearchSpec.SnippetSpec(
            return_snippet=True,
            max_snippet_count=5
        ),
        
        # Résumé IA optimisé
        summary_spec=discoveryengine_v1.SearchRequest.ContentSearchSpec.SummarySpec(
            summary_result_count=20,  # Plus de documents analysés
            include_citations=True,
            ignore_adversarial_query=True,
            ignore_non_summary_seeking_query=False,
            model_prompt_spec=discoveryengine_v1.SearchRequest.ContentSearchSpec.SummarySpec.ModelPromptSpec(
                preamble=system_prompt
            )
        )
        
        # Note: extractive_content_spec retiré car incompatible avec chunking config
    )
    
    request = discoveryengine_v1.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=25,  # Plus de résultats
        content_search_spec=content_search_spec,
        
        # Expansion automatique de la requête
        query_expansion_spec=discoveryengine_v1.SearchRequest.QueryExpansionSpec(
            condition=discoveryengine_v1.SearchRequest.QueryExpansionSpec.Condition.AUTO
        ),
        
        # Correction orthographique
        spell_correction_spec=discoveryengine_v1.SearchRequest.SpellCorrectionSpec(
            mode=discoveryengine_v1.SearchRequest.SpellCorrectionSpec.Mode.AUTO
        ),
        
        safe_search=True
    )
    
    return request

def execute_single_search(client, request):
    """Exécute une recherche unique"""
    try:
        return client.search(request)
    except Exception as e:
        print(f"⚠️  Erreur de recherche: {e}")
        return None

def select_best_result(responses):
    """Sélectionne automatiquement le meilleur résultat"""
    
    best_response = None
    best_score = 0
    
    for i, response in enumerate(responses):
        if not response:
            continue
        
        # Calcul du score de qualité
        result_count = len(list(response.results))
        has_summary = hasattr(response, 'summary') and response.summary and response.summary.summary_text
        
        citation_count = 0
        if hasattr(response, 'summary') and response.summary:
            if hasattr(response.summary, 'summary_with_metadata') and response.summary.summary_with_metadata:
                if hasattr(response.summary.summary_with_metadata, 'citations'):
                    citation_count = len(response.summary.summary_with_metadata.citations)
        
        # Score composite
        score = result_count * 2 + (50 if has_summary else 0) + citation_count * 10
        
        if score > best_score:
            best_score = score
            best_response = response
    
    return best_response

def execute_optimized_prompt(prompt_key: str, config: dict):
    """
    Version ultra-optimisée qui teste 3 stratégies et retourne automatiquement la meilleure
    """
    
    # Récupération du prompt
    prompt_data = None
    if config.get("prompts_config", {}).get(prompt_key):
        prompt_data = config["prompts_config"][prompt_key]
    elif config.get("prompts_config_final", {}).get(prompt_key):
        prompt_data = config["prompts_config_final"][prompt_key]
    
    if not prompt_data:
        print(f"❌ Variable '{prompt_key}' non trouvée")
        return None
    
    # Préparation
    base_query = replace_template_variables(prompt_data["prompt"], config)
    instructions = replace_template_variables(prompt_data.get("instructions", ""), config)
    base_instruction = config.get("default_settings", {}).get("base_instruction", "")
    if prompt_key in config.get("prompts_config_final", {}):
        base_instruction = config.get("default_settings", {}).get("base_instruction_final", base_instruction)
    
    system_prompt = f"{base_instruction}\n\n{instructions}" if instructions else base_instruction
    
    print(f"🎯 Variable: {prompt_key}")
    print("=" * 60)
    
    try:
        # Client
        with open("config.json", "r") as f:
            cred_config = json.load(f)
        credentials = service_account.Credentials.from_service_account_info(cred_config)
        client = discoveryengine_v1.SearchServiceClient(credentials=credentials)
        serving_config = f"projects/{PROJECT_ID}/locations/{LOCATION}/dataStores/{DATA_STORE_ID}/servingConfigs/default_config"
        
        # Création des 3 requêtes optimisées
        optimized_queries = create_optimized_queries(base_query, prompt_key)
        
        # Exécution en parallèle des 3 stratégies
        responses = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            for query in optimized_queries:
                request = create_optimized_request(query, prompt_key, system_prompt, serving_config)
                future = executor.submit(execute_single_search, client, request)
                futures.append(future)
            
            # Collecte des résultats
            for future in as_completed(futures):
                response = future.result()
                responses.append(response)
        
        # Sélection automatique du meilleur résultat
        best_response = select_best_result(responses)
        
        if not best_response:
            print("❌ Aucun résultat obtenu")
            return None
        
        # Affichage du meilleur résultat
        display_results(best_response)
        
        return best_response
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def display_results(response):
    """Affiche les résultats de manière claire et concise"""
    
    results = list(response.results)
    
    # Documents trouvés
    print(f"\n📋 {len(results)} documents analysés")
    
    # Top 8 documents
    print(f"\n📄 DOCUMENTS PERTINENTS:")
    print("-" * 50)
    
    for i, result in enumerate(results[:8], 1):
        doc = result.document
        
        # Nom du document
        doc_name = "Document inconnu"
        if hasattr(doc, 'struct_data') and doc.struct_data:
            uri = doc.struct_data.get('uri', '')
            if uri:
                doc_name = extract_document_name(uri)
            elif doc.struct_data.get('title'):
                doc_name = doc.struct_data.get('title')
        
        print(f"{i:2d}. 📄 {doc_name}")
        
        # Extraits pertinents
        if hasattr(result, 'document_metadata') and result.document_metadata:
            if hasattr(result.document_metadata, 'snippets') and result.document_metadata.snippets:
                for snippet in result.document_metadata.snippets[:2]:
                    if hasattr(snippet, 'snippet') and snippet.snippet:
                        snippet_text = snippet.snippet[:150] + "..." if len(snippet.snippet) > 150 else snippet.snippet
                        print(f"    💬 {snippet_text}")
        print()
    
    # Résumé IA
    if hasattr(response, 'summary') and response.summary:
        summary = response.summary
        
        print(f"🤖 RÉPONSE:")
        print("-" * 40)
        
        if hasattr(summary, 'summary_text') and summary.summary_text:
            print(summary.summary_text)
        else:
            print("Aucun résumé généré")
        
        # Sources citées
        if hasattr(summary, 'summary_with_metadata') and summary.summary_with_metadata:
            if hasattr(summary.summary_with_metadata, 'citations') and summary.summary_with_metadata.citations:
                citations = summary.summary_with_metadata.citations
                
                print(f"\n📚 BASÉ SUR LES DOCUMENTS:")
                print("-" * 40)
                
                cited_docs = set()
                for citation in citations:
                    if hasattr(citation, 'sources') and citation.sources:
                        for source in citation.sources:
                            if hasattr(source, 'uri') and source.uri:
                                doc_name = extract_document_name(source.uri)
                                if doc_name not in cited_docs:
                                    cited_docs.add(doc_name)
                                    print(f"• 📄 {doc_name}")
    
    print("\n" + "="*60)

def list_available_variables(config):
    """Affiche la liste des variables disponibles"""
    if not config:
        return []
    
    all_variables = []
    
    print("📋 VARIABLES DISPONIBLES:")
    print("=" * 50)
    
    # Variables principales
    if "prompts_config" in config:
        print("\n🔹 VARIABLES PRINCIPALES:")
        for key in config["prompts_config"].keys():
            all_variables.append(key)
            print(f"  • {key}")
    
    # Variables finales
    if "prompts_config_final" in config:
        print(f"\n🔹 VARIABLES FINALES:")
        for key in config["prompts_config_final"].keys():
            all_variables.append(key)
            print(f"  • {key}")
    
    return all_variables

def main():
    """Fonction principale simple"""
    
    print("🚀 EODEN - Recherche Ultra-Optimisée")
    print("=" * 60)
    
    # Charger la configuration
    config = load_prompts_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        return
    
    # Afficher les variables disponibles
    available_vars = list_available_variables(config)
    
    if not available_vars:
        print("❌ Aucune variable trouvée")
        return
    
    print(f"\nEntrez le nom de la variable à rechercher:")
    print("(ou tapez 'list' pour revoir la liste)")
    
    while True:
        try:
            choice = input(f"\nVariable > ").strip().upper()
            
            if choice.lower() in ['quit', 'exit', 'q']:
                print("👋 Au revoir !")
                break
            elif choice.lower() == 'list':
                list_available_variables(config)
                continue
            elif choice in available_vars:
                print()
                execute_optimized_prompt(choice, config)
            else:
                print(f"❌ Variable '{choice}' non trouvée. Tapez 'list' pour voir les variables disponibles.")
                
        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            break
        except Exception as e:
            print(f"\n❌ Erreur: {e}")

if __name__ == "__main__":
    main()