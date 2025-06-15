
```
joyit-cn-ai-rrhh-assistance
├─ .env
├─ app.py
├─ docker-compose.yml
├─ Dockerfile
├─ doc_llama
│  └─ ollama.py
├─ requirements.txt
└─ src
   ├─ adapters
   │  ├─ conversation_adapters
   │  │  ├─ conversation_management_adapter.py
   │  │  ├─ name_history_generator_adapter.py
   │  │  └─ __init__.py
   │  ├─ input_adapters
   │  │  ├─ api_controller.py
   │  │  └─ __init__.py
   │  ├─ output_adapters
   │  │  ├─ azure_repository.py
   │  │  ├─ chroma_repository.py
   │  │  ├─ gemini_repository.py
   │  │  ├─ mongo_repository.py
   │  │  ├─ ollama_repository.py
   │  │  └─ __init__.py
   │  ├─ tech_profile_adapters
   │  │  ├─ count_tokens_adapter.py
   │  │  ├─ process_request_cv_adapter.py
   │  │  ├─ process_request_requirements_adapter.py
   │  │  ├─ technical_report_prompt_generator_adapter.py
   │  │  └─ __init__.py
   │  └─ __init__.py
   ├─ domain
   │  ├─ entities
   │  │  ├─ test_case.py
   │  │  ├─ user_story.py
   │  │  └─ __init__.py
   │  ├─ services
   │  │  ├─ data_validation_service.py
   │  │  └─ __init__.py
   │  └─ __init__.py
   ├─ ports
   │  ├─ conversation_ports
   │  │  ├─ conversation_management_port.py
   │  │  ├─ name_history_generator_port.py
   │  │  └─ __init__.py
   │  ├─ input_ports
   │  │  ├─ api_port.py
   │  │  └─ __init__.py
   │  ├─ output_ports
   │  │  ├─ chromadb_repository_port.py
   │  │  ├─ llm_port.py
   │  │  ├─ mongo_port.py
   │  │  └─ __init__.py
   │  ├─ test_cases_ports
   │  │  ├─ count_tokens_port.py
   │  │  ├─ process_request_cv_port.py
   │  │  ├─ process_request_requirements_port.py
   │  │  ├─ test_case_prompt_generator_port.py
   │  │  └─ __init__.py
   │  └─ __init__.py
   ├─ services
   │  ├─ test_case_generator_service.py
   │  └─ __init__.py
   └─ __init__.py

```