output "cloud_run_service_uri" {
  description = "Deployed Cloud Run v2 endpoint URL for the Kuwait CAL ADK Agent."
  value       = google_cloud_run_v2_service.kuwait_cal_agent_service.uri
}

output "agent_service_account_email" {
  description = "Service Account email with least-privilege Vertex AI and Cloud Trace permissions."
  value       = google_service_account.kuwait_cal_agent_sa.email
}

output "cloud_scheduler_job_name" {
  description = "Sunday 06:00 Asia/Kuwait Cloud Scheduler job resource name."
  value       = google_cloud_scheduler_job.weekly_sunday_6am_dashboard.name
}
