from google.auth import default
import subprocess

def test_auth():
    creds, project_id = default()
    print(f"Default project_id: {project_id}")
    
    if not project_id:
        try:
            project_id = subprocess.check_output(["gcloud", "config", "get-value", "project"]).decode("utf-8").strip()
            print(f"Gcloud project_id: {project_id}")
        except Exception as e:
            print(f"Error getting gcloud project: {e}")
            project_id = None
            
    if hasattr(creds, 'with_quota_project') and project_id:
        print(f"Setting quota project to: {project_id}")
        creds = creds.with_quota_project(project_id)
        print("Successfully set quota project.")
    else:
        print("Could not set quota project (missing project_id or with_quota_project method).")

if __name__ == "__main__":
    test_auth()
