variable "supabase_org_id" {
  description = "The Organization ID for Supabase"
  type        = string
  sensitive   = true
}

variable "supabase_db_password" {
  description = "The password for the PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "supabase_access_token" {
  description = "The Personal Access Token for the Supabase Management API"
  type        = string
  sensitive   = true
}