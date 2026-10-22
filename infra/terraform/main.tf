terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Dedicated Least-Privilege Service Account for the Kuwait CAL ADK Agent
resource "google_service_account" "kuwait_cal_agent_sa" {
  account_id   = "kuwait-cal-agent-sa"
  display_name = "Kuwait CAL Executive Priority Dashboard ADK Agent SA"
  description  = "Service account for executing the Sunday 06:00 Asia/Kuwait ADK workflow on Cloud Run."
}

# Grant Vertex AI, Secret Manager, Cloud Trace, and Cloud Logging permissions
resource "google_project_iam_member" "agent_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
    "roles/cloudtrace.agent",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.kuwait_cal_agent_sa.email}"
}

# 2. Secret Manager Secret for Google Workspace CLI / OAuth Credentials
resource "google_secret_manager_secret" "workspace_oauth_config" {
  secret_id = "kuwait-cal-workspace-oauth"
  replication {
    auto {}
  }
}

# 3. Cloud Run v2 Service hosting the Python ADK 2.x Workflow & SQLite Volume
resource "google_cloud_run_v2_service" "kuwait_cal_agent_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.kuwait_cal_agent_sa.email
    timeout         = "600s"

    volumes {
      name = "sqlite_session_store"
      empty_dir {
        medium     = "MEMORY"
        size_limit = "512Mi"
      }
    }

    containers {
      image = var.container_image

      env {
        name  = "CAL_FLASH_MODEL"
        value = var.flash_model
      }
      env {
        name  = "CAL_PRO_MODEL"
        value = var.pro_model
      }
      env {
        name  = "CAL_SESSION_DB_PATH"
        value = "/var/lib/cal_agent/kuwait_cal_sessions.db"
      }
      env {
        name  = "WILLEM_EMAIL"
        value = var.authorized_self_email
      }
      env {
        name = "WORKSPACE_OAUTH_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.workspace_oauth_config.secret_id
            version = "latest"
          }
        }
      }

      volume_mounts {
        name       = "sqlite_session_store"
        mount_path = "/var/lib/cal_agent"
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }
  }
}

# Allow Cloud Scheduler to invoke the Cloud Run ADK Workflow Service
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.kuwait_cal_agent_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.kuwait_cal_agent_sa.email}"
}

# 4. Cloud Scheduler Job: Every Sunday at 06:00 AM Asia/Kuwait
resource "google_cloud_scheduler_job" "weekly_sunday_6am_dashboard" {
  name             = "weekly-kuwait-cal-dashboard-sunday-6am"
  description      = "Triggers the Kuwait CAL Executive Priority Dashboard ADK Agent every Sunday at 06:00 Asia/Kuwait."
  schedule         = "0 6 * * 0"
  time_zone        = "Asia/Kuwait"
  attempt_deadline = "540s"

  retry_config {
    retry_count          = 3
    min_backoff_duration = "10s"
    max_backoff_duration = "120s"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.kuwait_cal_agent_service.uri}/run"
    body = base64encode(json.encode({
      app_name = "kuwait_cal_dashboard_app"
      user_id  = "clappaert"
      state = {
        unattended_schedule = true
      }
    }))
    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.kuwait_cal_agent_sa.email
      audience              = google_cloud_run_v2_service.kuwait_cal_agent_service.uri
    }
  }
}
