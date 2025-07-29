#!/usr/bin/env python3
"""
Client Q&A EODEN Simple - Sélection directe de variable prompt
"""

import json
from google.cloud import discoveryengine_v1
from google.oauth2 import service_account

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
        import urllib.parse
        filename = urllib.parse.unquote(filename)
        return filename
    
    return "Document sans nom"

def execute_prompt(prompt_key: str, config: dict):
    """
    Exécute un prompt spécifique et retourne la réponse
    
    Args:
        prompt_key: Clé du prompt dans la configuration
        config: Configuration des prompts
    """
    
    # Rechercher le prompt dans les deux sections
    prompt_data = None
    if config.get("prompts_config", {}).get(prompt_key):
        prompt_data = config["prompts_config"][prompt_key]
    elif config.get("prompts_config_final", {}).get(prompt_key):
        prompt_data = config["prompts_config_final"][prompt_key]
    
    if not prompt_data:
        print(f"❌ Erreur: Variable '{prompt_key}' non trouvée dans la configuration")
        return None
    
    # Récupérer le prompt et remplacer les variables
    question = replace_template_variables(prompt_data["prompt"], config)
    instructions = replace_template_variables(prompt_data.get("instructions", ""), config)
    
    # Construire le prompt système complet
    base_instruction = config.get("default_settings", {}).get("base_instruction", "")
    if prompt_key in config.get("prompts_config_final", {}):
        base_instruction = config.get("default_settings", {}).get("base_instruction_final", base_instruction)
    
    system_prompt = f"{base_instruction}\n\n{instructions}" if instructions else base_instruction
    
    print(f"🎯 Variable: {prompt_key}")
    print("=" * 60)
    
    try:
        # Charger les credentials
        with open("config.json", "r") as f:
            cred_config = json.load(f)
        credentials = service_account.Credentials.from_service_account_info(cred_config)
        
        # Client de recherche
        client = discoveryengine_v1.SearchServiceClient(credentials=credentials)
        
        # Serving config
        serving_config = f"projects/{PROJECT_ID}/locations/{LOCATION}/dataStores/{DATA_STORE_ID}/servingConfigs/default_config"
        
        # Configuration pour réponse générée avec prompt système personnalisé
        content_search_spec = discoveryengine_v1.SearchRequest.ContentSearchSpec(
            snippet_spec=discoveryengine_v1.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True,
                max_snippet_count=3
            ),
            summary_spec=discoveryengine_v1.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=10,
                include_citations=True,
                ignore_adversarial_query=True,
                ignore_non_summary_seeking_query=False,
                model_prompt_spec=discoveryengine_v1.SearchRequest.ContentSearchSpec.SummarySpec.ModelPromptSpec(
                    preamble=system_prompt
                )
            )
        )
        
        # Requête avec génération de réponse
        request = discoveryengine_v1.SearchRequest(
            serving_config=serving_config,
            query=question,
            page_size=10,
            content_search_spec=content_search_spec,
            query_expansion_spec=discoveryengine_v1.SearchRequest.QueryExpansionSpec(
                condition=discoveryengine_v1.SearchRequest.QueryExpansionSpec.Condition.AUTO
            )
        )
        
        # Recherche
        response = client.search(request=request)
        
        # Afficher les noms des fichiers trouvés
        for i, result in enumerate(response.results, 1):
            doc = result.document
            doc_id = getattr(doc, "id", "inconnu")
            # Essayer d'abord struct_data, sinon derived_struct_data
            struct_data = getattr(doc, "struct_data", {}) or {}
            if not struct_data:
                struct_data = getattr(doc, "derived_struct_data", {}) or {}
            # Si struct_data est un objet type protobuf Struct, convertir en dict
            if hasattr(struct_data, "fields"):
                struct_data = {k: v.string_value if hasattr(v, "string_value") else v for k, v in struct_data.fields.items()}
            title = struct_data.get("title", "Titre inconnu")
            link = struct_data.get("link", "Lien inconnu")
            print(f"{i}. {title} (ID: {doc_id})")
            print(f"   Lien : {link}")
        
        # Collecter les noms des documents sources
        results = list(response.results)
        document_mapping = {}
        
        # Créer un mapping des documents depuis les résultats de recherche
        for result in results:
            doc = result.document
            reference_id = doc.id if hasattr(doc, 'id') else None
            
            doc_name = "Document inconnu"
            if hasattr(doc, 'struct_data') and doc.struct_data:
                uri = doc.struct_data.get('uri', '')
                if uri:
                    doc_name = extract_document_name(uri)
                
                if doc_name == "Document inconnu" or not doc_name:
                    title = doc.struct_data.get('title', '')
                    if title:
                        doc_name = title
                    else:
                        name = doc.struct_data.get('name', '')
                        if name:
                            doc_name = name
            
            if reference_id:
                document_mapping[reference_id] = doc_name

        # Afficher la réponse générée
        if hasattr(response, 'summary') and response.summary:
            summary = response.summary
            
            print("🤖 RÉPONSE:")
            print("-" * 40)
            
            if hasattr(summary, 'summary_text') and summary.summary_text:
                print(summary.summary_text)
            else:
                print("Aucun résumé généré")
            
            # Collecter les documents sources depuis les citations
            citation_sources = set()
            if hasattr(summary, 'summary_with_metadata') and summary.summary_with_metadata:
                if hasattr(summary.summary_with_metadata, 'citations') and summary.summary_with_metadata.citations:
                    for citation in summary.summary_with_metadata.citations:
                        if hasattr(citation, 'sources') and citation.sources:
                            for source in citation.sources:
                                ref_id = source.reference_id if hasattr(source, 'reference_id') else None
                                if ref_id and ref_id in document_mapping:
                                    citation_sources.add(document_mapping[ref_id])
                                elif hasattr(source, 'uri') and source.uri:
                                    doc_name = extract_document_name(source.uri)
                                    citation_sources.add(doc_name)
            
            # Afficher les sources avec liens détaillés
            if not citation_sources and results:
                print(f"\n📋 BASÉ SUR LES DOCUMENTS (premiers résultats pertinents):")
                print("-" * 40)
                for i, result in enumerate(results[:5], 1):
                    doc = result.document
                    doc_name = "Document inconnu"
                    if hasattr(doc, 'struct_data') and doc.struct_data:
                        uri = doc.struct_data.get('uri', '')
                        if uri:
                            doc_name = extract_document_name(uri)
                        elif doc.struct_data.get('title'):
                            doc_name = doc.struct_data.get('title')
                    print(f"{i}. 📄 {doc_name}")
            elif citation_sources:
                print(f"\n📋 BASÉ SUR LES DOCUMENTS:")
                print("-" * 40)
                for i, doc_name in enumerate(sorted(citation_sources), 1):
                    print(f"{i}. 📄 {doc_name}")
            
            print("\n📚 SOURCES DÉTAILLÉES:")
            print("-" * 40)
            
            # Afficher les sources avec citations détaillées
            if hasattr(summary, 'summary_with_metadata') and summary.summary_with_metadata:
                if hasattr(summary.summary_with_metadata, 'citations') and summary.summary_with_metadata.citations:
                    print(f"Nombre de sources utilisées: {len(summary.summary_with_metadata.citations)}")
                    print()
                    for i, citation in enumerate(summary.summary_with_metadata.citations, 1):
                        if hasattr(citation, 'sources') and citation.sources:
                            for source in citation.sources:
                                ref_id = source.reference_id if hasattr(source, 'reference_id') else "Non spécifié"
                                doc_name = document_mapping.get(ref_id, "Document non identifié")
                                
                                print(f"{i}. 📄 Source: {ref_id}")
                                print(f"   📁 Document: {doc_name}")
                                
                                if hasattr(source, 'uri') and source.uri:
                                    print(f"   🔗 {source.uri}")
                                print()
                else:
                    print("Aucune citation détaillée disponible")
        
        # Afficher aussi les résultats de recherche classiques
        if results:
            print(f"\n🔍 DOCUMENTS PERTINENTS ({len(results)} trouvés):")
            print("-" * 40)
            
            for i, result in enumerate(results[:5], 1):
                doc = result.document
                
                # Nom du fichier depuis l'URI
                doc_name = "Document"
                if hasattr(doc, 'struct_data') and doc.struct_data:
                    uri = doc.struct_data.get('uri', '')
                    if uri:
                        doc_name = extract_document_name(uri)
                
                print(f"{i}. 📄 {doc_name}")
                
                # Extraits pertinents
                if hasattr(result, 'document_metadata') and result.document_metadata:
                    if hasattr(result.document_metadata, 'snippets') and result.document_metadata.snippets:
                        for snippet in result.document_metadata.snippets[:2]:
                            if hasattr(snippet, 'snippet') and snippet.snippet:
                                print(f"   💬 {snippet.snippet}")
                
                print()
        
        return response
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        print(f"💡 Vérifiez que les fonctionnalités Enterprise sont activées")
        return None

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
    """Fonction principale"""
    
    print("🚀 EODEN - Test Variable Prompt")
    print("=" * 60)
    
    # Charger la configuration des prompts
    config = load_prompts_config()
    if not config:
        print("❌ Impossible de charger la configuration des prompts")
        return
    
    # Afficher les variables disponibles
    available_vars = list_available_variables(config)
    
    if not available_vars:
        print("❌ Aucune variable trouvée dans la configuration")
        return
    
    # Demander quelle variable tester
    print(f"\nEntrez le nom de la variable à tester:")
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
                execute_prompt(choice, config)
                break
            else:
                print(f"❌ Variable '{choice}' non trouvée. Tapez 'list' pour voir les variables disponibles.")
                
        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            break
        except Exception as e:
            print(f"\n❌ Erreur: {e}")

if __name__ == "__main__":
    main()