terraform {
  required_providers {
    supabase = {
      source  = "supabase/supabase"
      version = "~> 1.0"
    }
  }
}

# The provider automatically reads the SUPABASE_ACCESS_TOKEN environment variable
provider "supabase" {
  access_token = var.supabase_access_token
}

# Provision the free-tier PostgreSQL database
resource "supabase_project" "rag_backend" {
  organization_id   = var.supabase_org_id
  name              = "ai-rag-database"
  database_password = var.supabase_db_password
  region            = "us-east-1"
  
  lifecycle {
    ignore_changes = [database_password]
  }
}