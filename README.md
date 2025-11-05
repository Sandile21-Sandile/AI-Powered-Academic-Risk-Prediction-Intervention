# AI-Powered Academic Risk Prediction & Intervention

This repository contains a student risk prediction project (Python / Flask). This README was added to help you publish the project to GitHub.

Quick steps to push this local project to GitHub (PowerShell):

1. Install Git for Windows and restart PowerShell if needed.
   - Download: https://git-scm.com/download/win
   - Or (if you have winget): `winget install --id Git.Git -e --source winget`

2. Configure your Git identity (replace with your details):

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

3. Initialize repo, commit, and push (run from project root):

```powershell
cd "C:\Users\230000473\Downloads\Final Year Project (2)\Final Year Project"
# initialize
git init
# add all files
git add .
# commit
git commit -m "Initial commit"
# create main branch (optional but recommended)
git branch -M main
# add remote (replace <your-repo-url>)
git remote add origin https://github.com/<your-username>/<your-repo>.git
# push
git push -u origin main
```

4. Optional: generate requirements.txt from your virtual environment:

```powershell
pip freeze > requirements.txt
```

Notes:
- If you prefer SSH, set up an SSH key and use the SSH remote URL instead of HTTPS.
- If you want, create the GitHub repo from the web UI and copy the remote URL into the `git remote add origin` command above.

If you'd like, I can:
- Create a `requirements.txt` by scanning the project (needs your virtualenv),
- Initialize the git repo and perform the first commit from here (requires Git installed on your machine), or
- Help create the GitHub repo using the GitHub CLI if you have it installed.
