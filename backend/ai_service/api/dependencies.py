from backend.ai_service.application.orchestrator import OrchestratorService
from backend.ai_service.knowledge.service import KnowledgeService
from backend.ai_service.storage.factory import create_history_service, create_vector_store


vector_store = create_vector_store()
knowledge_service = KnowledgeService(vector_store=vector_store)
history_service = create_history_service()
orchestrator_service = OrchestratorService(
    vector_store=vector_store,
    history_service=history_service,
)
