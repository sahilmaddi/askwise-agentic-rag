output "web_url" {
  description = "Public URL of the Askwise web app."
  value       = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "application_insights_name" {
  description = "Application Insights resource with the API's traces and metrics (connect it to Azure AI Foundry)."
  value       = azurerm_application_insights.main.name
}

output "vector_store" {
  description = "Vector store the API uses."
  value       = local.vector_store
}
