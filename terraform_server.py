#!/usr/bin/env python3
import asyncio
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional

# ---------------------------
# Pydantic Models
# ---------------------------

class TerraformTemplateRequest(BaseModel):
    name: str = Field(..., description="Name of the Terraform module to generate")
    cloud: str = Field(..., description="Cloud provider (aws, gcp, azure)")
    resource: str = Field(..., description="Resource type (vm, bucket, sql, vpc, etc.)")

class TerraformTroubleshootRequest(BaseModel):
    error_message: str = Field(..., description="Raw Terraform CLI error output")
# ---------------------------
# Server Init
# ---------------------------

server = FastMCP("tf-devops-server")
# server exposes resources(file, document pdf movies, api responses like list, get), tools
# function that could be executed, and prompts(prompt placeholder)

# ---------------------------
# Tool: Terraform Template Generator
# ---------------------------

@server.tool()
async def generate_terraform_template(body: TerraformTemplateRequest):
    """
    Generates a Terraform template skeleton based on cloud + resource type.
    """
    module_name = body.name.lower().replace(" ", "_")

    template = f"""
    # Auto-generated Terraform Module: {body.name}

    terraform {{
      required_version = ">= 1.3.0"
      required_providers {{
        {body.cloud} = {{
          source  = "hashicorp/{body.cloud}"
          version = "~> 5.0"
        }}
      }}
    }}

    provider "{body.cloud}" {{
      # configuration here
    }}

    # Example resource block
    resource "{body.cloud}_{body.resource}" "{module_name}" {{
      # add arguments here
    }}

    output "id" {{
      value = {body.cloud}_{body.resource}.{module_name}.id
    }}
    """

    return {"template": template.strip()}

# ---------------------------
# Tool: Terraform Troubleshooting
# ---------------------------

@server.tool()
async def troubleshoot_terraform(body: TerraformTroubleshootRequest):
    """
    Returns structured reasons + potential fixes for Terraform errors.
    """

    err = body.error_message.lower()

    if "authentication" in err or "403" in err:
        return {
            "reason": "Credentials or token invalid.",
            "suggestions": [
                "Ensure cloud provider credentials are exported.",
                "Check service account or IAM permissions.",
                "Run `terraform init` again."
            ]
        }

    if "timeout" in err:
        return {
            "reason": "Network or provider API unreachable.",
            "suggestions": [
                "Check firewall / proxy.",
                "Retry with increased timeouts.",
            ]
        }

    if "no such file" in err:
        return {
            "reason": "Terraform module or file missing.",
            "suggestions": [
                "Check module path.",
                "Run from correct working directory."
            ]
        }

    return {
        "reason": "Unknown error (not matched by heuristics).",
        "suggestions": [
            "Re-run with TF_LOG=DEBUG",
            "Check provider docs"
        ]
    }

if __name__ == "__main__":
    server.run()
