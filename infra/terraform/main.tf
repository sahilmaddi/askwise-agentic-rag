# Askwise on Azure Container Apps:
#   web (public ingress) ─▶ api (internal ingress) ─▶ Azure OpenAI / Azure AI Search
#   api telemetry ─▶ Application Insights (OpenTelemetry via Azure Monitor), viewable in Azure AI Foundry
#   FAISS index and SQLite registry ─▶ Azure Files share mounted at /data

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  suffix       = random_string.suffix.result
  vector_store = var.enable_ai_search ? "azure_search" : "faiss"
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.name}"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.name}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.name}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}

resource "azurerm_storage_account" "main" {
  name                     = "st${var.name}${local.suffix}"
  location                 = azurerm_resource_group.main.location
  resource_group_name      = azurerm_resource_group.main.name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_share" "data" {
  name               = "askwise-data"
  storage_account_id = azurerm_storage_account.main.id
  quota              = 10
}

resource "azurerm_search_service" "main" {
  count               = var.enable_ai_search ? 1 : 0
  name                = "srch-${var.name}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "basic"
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.name}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

resource "azurerm_container_app_environment_storage" "data" {
  name                         = "askwise-data"
  container_app_environment_id = azurerm_container_app_environment.main.id
  account_name                 = azurerm_storage_account.main.name
  share_name                   = azurerm_storage_share.data.name
  access_key                   = azurerm_storage_account.main.primary_access_key
  access_mode                  = "ReadWrite"
}

resource "azurerm_container_app" "api" {
  name                         = "${var.name}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  secret {
    name  = "azure-openai-api-key"
    value = var.azure_openai_api_key != "" ? var.azure_openai_api_key : "unset"
  }
  secret {
    name  = "appinsights-connection-string"
    value = azurerm_application_insights.main.connection_string
  }
  secret {
    name  = "azure-search-key"
    value = var.enable_ai_search ? azurerm_search_service.main[0].primary_key : "unset"
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # One replica: the FAISS index is a single file set on the share. With Azure AI Search, raise this.
    min_replicas = 1
    max_replicas = var.enable_ai_search ? 3 : 1

    container {
      name   = "api"
      image  = var.api_image
      cpu    = 1
      memory = "2Gi"

      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name  = "EMBEDDINGS_PROVIDER"
        value = var.embeddings_provider
      }
      env {
        name  = "EMBEDDINGS_MODEL"
        value = var.embeddings_model
      }
      env {
        name  = "VECTOR_STORE"
        value = local.vector_store
      }
      env {
        name  = "SEED_SAMPLES"
        value = "true"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "OPENAI_API_VERSION"
        value = "2024-10-21"
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-openai-api-key"
      }
      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = var.enable_ai_search ? "https://${azurerm_search_service.main[0].name}.search.windows.net" : ""
      }
      env {
        name        = "AZURE_SEARCH_KEY"
        secret_name = "azure-search-key"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }

      volume_mounts {
        name = "data"
        path = "/data"
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/api/health"
      }
    }

    volume {
      name         = "data"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.data.name
    }
  }
}

resource "azurerm_container_app" "web" {
  name                         = "${var.name}-web"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  ingress {
    external_enabled = true
    target_port      = 80
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "web"
      image  = var.web_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        # Apps in one Container Apps environment reach each other by name over internal ingress.
        name  = "API_URL"
        value = "http://${var.name}-api"
      }
    }
  }
}
