variable "name" {
  description = "Prefix for every resource name."
  type        = string
  default     = "askwise"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "centralindia"
}

variable "api_image" {
  description = "Container image for the API, e.g. ghcr.io/<you>/askwise-api:1.0.0"
  type        = string
}

variable "web_image" {
  description = "Container image for the web front end."
  type        = string
}

variable "llm_provider" {
  description = "LLM_PROVIDER for the API: azure, openai, mistral, ollama or extractive."
  type        = string
  default     = "azure"
}

variable "llm_model" {
  description = "Chat model or Azure OpenAI deployment name."
  type        = string
  default     = "gpt-4o-mini"
}

variable "embeddings_provider" {
  description = "EMBEDDINGS_PROVIDER for the API: azure, openai, cohere, fastembed or hashing."
  type        = string
  default     = "azure"
}

variable "embeddings_model" {
  description = "Embedding model or Azure OpenAI deployment name."
  type        = string
  default     = "text-embedding-3-small"
}

variable "azure_openai_endpoint" {
  description = "Existing Azure OpenAI endpoint (models are deployed separately because they need quota)."
  type        = string
  default     = ""
}

variable "azure_openai_api_key" {
  description = "Azure OpenAI key, stored as a Container Apps secret."
  type        = string
  default     = ""
  sensitive   = true
}

variable "enable_ai_search" {
  description = "Create an Azure AI Search service and use it as the vector store instead of FAISS."
  type        = bool
  default     = false
}
