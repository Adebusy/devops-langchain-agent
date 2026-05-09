import os
import requests
from mcp.server.fastmcp import FastMCP, Context

GITLAB_URL =  "" #os.environ.get("GITLAB_API_URL", "").rstrip("/") coreai-platform-gcp/coreai-apps-gcp-manifest
GITLAB_TOKEN = ""#os.environ.get("GITLAB_PERSONAL_ACCESS_TOKEN", "")

if not GITLAB_URL or not GITLAB_TOKEN:
    raise RuntimeError("GITLAB_API_URL and GITLAB_PERSONAL_ACCESS_TOKEN must be set")

# Configure MCP server
mcp = FastMCP("gitlab")

HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN,
    "Content-Type": "application/json"
}

def gitlab_commit(project_id: str, branch: str, commit_message: str, actions: list):
    """
    Create a commit in a GitLab repo.

    actions is a list of dicts:
    [
        {
            "action": "create" | "update" | "delete" | "move",
            "file_path": "path/to/file",
            "content": "file content"
        }
    ]
    """
    payload = {
        "branch": branch,
        "commit_message": commit_message,
        "actions": actions
    }
    return gitlab_post(f"/projects/{project_id}/repository/commits", payload)

def gitlab_get(path, params=None):
    url = f"{GITLAB_URL}/api/v4{path}"
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def gitlab_post(path, json_body):
    url = f"{GITLAB_URL}/api/v4{path}"
    r = requests.post(url, headers=HEADERS, json=json_body)
    r.raise_for_status()
    return r.json()

def gitlab_get(path):
    url = f"{GITLAB_URL}/api/v4{path}"
    r = requests.get(url, headers=HEADERS)
    if not r.ok:
        return f"GitLab API error {r.status_code}: {r.text}"
    return r.json()

def gitlab_create_branch(project_id: str, branch_name: str, ref: str = "main"):
    """
    Create a new branch from an existing ref (default: main).
    """
    payload = {
        "branch": branch_name,
        "ref": ref
    }
    return gitlab_post(f"/projects/{project_id}/repository/branches", payload)

def ensure_branch_exists(project_id, branch_name, ref="main"):
    try:
        gitlab_get(f"/projects/{project_id}/repository/branches/{branch_name}")
        return
    except:
        return gitlab_create_branch(project_id, branch_name, ref)

@mcp.tool()
def list_projects() -> str:
    """List GitLab projects available to the PAT."""
    data = gitlab_get("/projects?membership=true&simple=true&per_page=100")
    if isinstance(data, str):
        return data
    return "\n".join([f"{p['id']} - {p['name']}" for p in data])

@mcp.tool()
def list_branches(project_id: str) -> str:
    """List branches for a project."""
    data = gitlab_get(f"/projects/{project_id}/repository/branches")
    if isinstance(data, str):
        return data
    return "\n".join([b["name"] for b in data])

@mcp.tool()
def get_file(project_id: str, filepath: str, ref: str = "main") -> str:
    """Fetch a file from a GitLab repository."""
    path = f"/projects/{project_id}/repository/files/{requests.utils.quote(filepath, safe='')}"
    data = gitlab_get(f"{path}?ref={ref}")

    if isinstance(data, str):
        return data

    import base64
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content

@mcp.tool()
def get_pipeline_status(project_id: str) -> str:
    """List recent pipelines for a project."""
    data = gitlab_get(f"/projects/{project_id}/pipelines")
    if isinstance(data, str):
        return data
    return "\n".join([f"ID {p['id']} - Status {p['status']}" for p in data])

@mcp.tool()
def create_branch(body: dict) -> str:
    """
    Create a new branch in a GitLab project.

    body must contain:
      - project_id (str or int)
      - branch_name (str)
    Optional:
      - ref (str): default 'main'
    """
    if "project_id" not in body or "branch_name" not in body:
        return "Missing required fields: project_id, branch_name"

    ref = body.get("ref", "main")

    try:
        branch = gitlab_create_branch(body["project_id"], body["branch_name"], ref)
        return f"Created branch: {branch.get('name')} (web URL: {branch.get('web_url')})"
    except Exception as e:
        return f"Error creating branch: {e}"

@mcp.tool()
def commit_changes(body: dict) -> str:
    """
    Commit file changes to a GitLab project.

    Required:
      project_id (str or int)
      branch (str)
      commit_message (str)
      file_path (str)xw
      content (str)

    Optional:
      action: 'create' | 'update' | 'delete' | 'move'
      ref: branch to branch from when auto-creating (default: main)
    """

    required = ["project_id", "branch", "commit_message", "file_path", "content"]
    for f in required:
        if f not in body:
            return f"Missing required field `{f}`"

    project_id = body["project_id"]
    branch = body["branch"]
    file_path = body["file_path"]
    content = body["content"]
    commit_message = body["commit_message"]

    action = body.get("action", "update")  # default to update
    ref = body.get("ref", "main")

    try:
        ensure_branch_exists(project_id, branch, ref)
    except Exception as e:
        return f"Failed to ensure branch exists: {e}"

    actions = [{
        "action": action,
        "file_path": file_path,
        "content": content
    }]

    try:
        commit = gitlab_commit(project_id, branch, commit_message, actions)
        return f"Commit created: {commit.get('web_url', commit)}"
    except Exception as e:
        return f"GitLab commit error: {e}"

@mcp.tool()
def create_merge_request(body: dict) -> str:
    required = ["project_id", "source_branch", "target_branch", "title"]
    for f in required:
        if f not in body:
            return f"Missing required field `{f}`"

    project_id = body["project_id"]
    source_branch = body["source_branch"]

    # auto-create branch if missing
    try:
        ensure_branch_exists(project_id, source_branch, ref=body.get("ref", "main"))
    except Exception as e:
        return f"Failed to create or verify source branch: {e}"

    payload = {
        "source_branch": source_branch,
        "target_branch": body["target_branch"],
        "title": body["title"]
    }

    if "description" in body:
        payload["description"] = body["description"]

    try:
        mr = gitlab_post(f"/projects/{project_id}/merge_requests", payload)
        return f"MR created: {mr.get('web_url')}"
    except Exception as e:
        return f"GitLab error creating MR: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
