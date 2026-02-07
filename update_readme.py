import requests
import os

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
ORG_NAME = 'HITSZ-OpenAuto'

def get_repos(org_name, access_token):
    url = f'https://api.github.com/orgs/{org_name}/repos'
    headers = {'Authorization': f'token {access_token}'}
    repos = []
    
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        repos.extend(repo['name'] for repo in data if repo['name'] != '.github' and repo['name'] != 'hoa.moe' and not repo['private'])   
        url = response.links.get('next', {}).get('url')
    
    return repos

def generate_contributors_url(org_name):
    # Keep this URL short to avoid GitHub README rendering errors ("URI Too Long").
    # The contrib service will expand org → repo list server-side.
    base_url = "https://contrib.hoa.moe/api"
    params = [
        f"org={org_name}",
        # Mirror previous exclusions from get_repos()
        "exclude=.github",
        "exclude=hoa.moe",
        # Extra repo outside the org
        "repo=noname7321/HITSZ-OpenAuto",
    ]
    return base_url + "?" + "&".join(params)

def update_readme(readme_path, new_url):
    with open(readme_path, 'r') as file:
        lines = file.readlines()

    with open(readme_path, 'w') as file:
        for line in lines:
            if line.strip().startswith("![Contributors]"):
                file.write(f"![Contributors]({new_url})\n")
            else:
                file.write(line)

if __name__ == "__main__":

    # Still fetch repos to keep the existing behavior of requiring ACCESS_TOKEN
    # (and to allow easy future extensions), but we no longer embed the full list
    # into the README image URL.
    get_repos(ORG_NAME, ACCESS_TOKEN)

    readme_file_path = 'profile/README.md'
    new_contributors_url = generate_contributors_url(ORG_NAME)
    update_readme(readme_file_path, new_contributors_url)
