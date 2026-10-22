variable "project_id" {
  description = "Google Cloud Project ID hosting the Kuwait CAL Executive Dashboard Agent."
  type        = string
}

variable "region" {
  description = "Primary GCP region (e.g., me-central1 or europe-west1)."
  type        = string
  default     = "me-central1"
}

variable "service_name" {
  description = "Cloud Run v2 service name."
  type        = string
  default     = "kuwait-cal-dashboard-agent"
}

variable "container_image" {
  description = "Artifact Registry container image URI for the ADK agent."
  type        = string
  default     = "me-central1-docker.pkg.dev/kuwait-cal-prod/agents/kuwait-cal-agent:latest"
}

variable "flash_model" {
  description = "Fast structured extraction Gemini model tier."
  type        = string
  default     = "gemini-3.8-flash"
}

variable "pro_model" {
  description = "Deep reasoning, strategic ideation, and LLM-as-a-Judge Gemini model tier."
  type        = string
  default     = "gemini-3.1-pro"
}

variable "authorized_self_email" {
  description = "Strictly allowlisted self-digest email recipient."
  type        = string
  default     = "clappaert@google.com"
}
