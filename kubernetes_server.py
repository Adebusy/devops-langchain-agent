from mcp.server.fastmcp import FastMCP
from kubernetes import client, config
import yaml
import sys
from typing import Dict, Any

server = FastMCP("kubernetes")
try:
    print("Loading kubeconfig...", file=sys.stderr)
    config.load_kube_config(config_file="/Users/ramalao/.kube/config", context="aks-coreapp-dev-eastus2-001")
    print("Kubeconfig loaded successfully!", file=sys.stderr)

    c = client.Configuration.get_default_copy()
    print(f"Kube API host: {c.host}", file=sys.stderr)
    print(f"Auth token present: {bool(c.api_key)}", file=sys.stderr)

except Exception as e:
    print(f"ERROR loading kubeconfig: {e}", file=sys.stderr)
    raise

core = client.CoreV1Api()
apps = client.AppsV1Api()

def generate_advice(reason: str, cs, pod):
    """
    Given a container reason, return remediation advice.
    """

    reason = reason or ""
    reason_lower = reason.lower()

    if reason_lower == "crashloopbackoff":
        return [
            "Check container logs: `kubectl logs {pod} -c {container}`.",
            "Verify app startup command is correct.",
            "Look for incorrect environment variables or missing configs.",
            "Check if readiness/liveness probes are misconfigured."
        ]

    if reason_lower in ["imagepullbackoff", "errimagepull"]:
        return [
            "Verify the image name, tag, and registry path.",
            "Check if the image exists in the registry.",
            "Ensure the service account has correct imagePullSecrets.",
            "Confirm container registry credentials (GCR, DockerHub, etc.)."
        ]

    if reason_lower == "oomkilled":
        return [
            "Increase memory limits or requests.",
            "Check the app for memory leaks.",
            "Inspect memory usage using Metrics Server.",
            "Consider adding resource limits to prevent node pressure."
        ]

    if reason_lower == "createcontainerconfigerror":
        return [
            "Check volume mounts and ConfigMap/Secret keys.",
            "Ensure any referenced Secret or ConfigMap exists.",
            "Validate container command and args."
        ]

    if reason_lower == "terminated":
        return [
            "Review container logs.",
            "Check exit code and failure mode.",
            "Validate startup/shutdown logic."
        ]

    return [
        f"No predefined advice for reason '{reason}'.",
        "Check pod logs and describe output:",
        f"`kubectl describe pod {pod.metadata.name}`",
        f"`kubectl logs {pod.metadata.name} -c {cs.name}`"
    ]

def pod_pending_advice(pod):
    """
    Advise on Pods stuck in Pending state
    """
    return [
        "Check for insufficient cluster resources (CPU/memory).",
        "Check node taints: `kubectl describe node`.",
        "Verify pod nodeSelector, affinity, or tolerations.",
        "Check if PVCs are bound if using PersistentVolumes."
    ]

@server.tool()
def list_pods(namespace: str, status: str = None) -> dict:
    """
    List pods in a namespace, optionally filtered by status.
    """

    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)

    results = []

    for pod in pods.items:
        pod_status = pod.status.phase  # Running, Pending, Failed, etc.

        # CrashLoopBackOff and container-level states
        detailed_status = None
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                if cs.state.waiting and cs.state.waiting.reason:
                    detailed_status = cs.state.waiting.reason

        # If filtering by status:
        if status:
            # Normalize case
            s = status.lower()

            # Match phase, like "Running"
            if pod_status.lower() == s:
                pass
            # Match container-level failures, like CrashLoopBackOff
            elif detailed_status and detailed_status.lower() == s:
                pass
            else:
                continue  # skip pod

        results.append({
            "name": pod.metadata.name,
            "phase": pod_status,
            "reason": detailed_status,
            "node": pod.spec.node_name
        })

    return {"pods": results}

@server.tool()
def describe_pod(name: str, namespace: str = "default"):
    """Return details about a pod."""
    pod = core.read_namespaced_pod(name=name, namespace=namespace)
    return pod.to_dict()

@server.tool()
def get_logs(name: str, namespace: str = "default", container: str = None):
    """Fetch logs from a container or pod."""
    logs = core.read_namespaced_pod_log(
        name=name,
        namespace=namespace,
        container=container
    )
    return logs

@server.tool()
def delete_resource(kind: str, name: str, namespace: str = "default"):
    """Delete a resource (pod, deployment, job)."""
    kind = kind.lower()

    if kind == "pod":
        return core.delete_namespaced_pod(name, namespace).to_dict()

    if kind == "deployment":
        return apps.delete_namespaced_deployment(name, namespace).to_dict()

    raise ValueError("Unsupported resource kind")

@server.tool()
def list_deployments(namespace: str = "default"):
    """List all deployments in a namespace."""
    deployments = apps.list_namespaced_deployment(namespace)
    return [d.metadata.name for d in deployments.items]

@server.tool()
def restart_deployment(name: str, namespace: str = "default"):
    """Equivalent to `kubectl rollout restart deployment`."""
    body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": "now"
                    }
                }
            }
        }
    }
    deployment = apps.patch_namespaced_deployment(name, namespace, body)
    return deployment.to_dict()

@server.tool()
def apply_yaml(yaml_content: str, namespace: str = "default"):
    """Apply a YAML manifest (like kubectl apply)."""
    doc = yaml.safe_load(yaml_content)

    kind = doc["kind"].lower()
    metadata = doc["metadata"]
    name = metadata["name"]

    if kind == "pod":
        return core.create_namespaced_pod(namespace, doc).to_dict()

    if kind == "deployment":
        return apps.create_namespaced_deployment(namespace, doc).to_dict()

    raise ValueError("Unsupported resource in apply")

@server.tool()
def diagnose_pod_issues(namespace: str) -> Dict[str, Any]:
    """
    Scan pods in a namespace for errors and provide actionable recommendations.
    Returns a list of problematic pods with root cause analysis and remediation steps.
    """

    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)

    diagnostics = []

    for pod in pods.items:
        pod_name = pod.metadata.name
        phase = pod.status.phase
        node = pod.spec.node_name

        container_status_list = pod.status.container_statuses or []

        pod_issues = []

        for cs in container_status_list:
            reason = None
            message = None

            # Check waiting state
            if cs.state.waiting:
                reason = cs.state.waiting.reason
                message = cs.state.waiting.message

            # Check terminated state
            elif cs.state.terminated:
                reason = cs.state.terminated.reason
                message = cs.state.terminated.message

            # Check OOM
            if cs.last_state.terminated and cs.last_state.terminated.reason == "OOMKilled":
                reason = "OOMKilled"
                message = "Container was killed due to out-of-memory condition."

            if reason:
                pod_issues.append({
                    "container": cs.name,
                    "reason": reason,
                    "message": message,
                    "advice": generate_advice(reason, cs, pod)
                })

        # Also detect pod-level failures (no containers started)
        if phase == "Pending":
            pod_issues.append({
                "container": None,
                "reason": "Pending",
                "message": "Pod pending scheduling.",
                "advice": pod_pending_advice(pod)
            })

        if pod_issues:
            diagnostics.append({
                "pod": pod_name,
                "node": node,
                "phase": phase,
                "issues": pod_issues
            })

    return {"diagnostics": diagnostics}

if __name__ == "__main__":
    server.run()
