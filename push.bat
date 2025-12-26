@echo off
echo Pushing to GitHub...
git add .
git commit -m "Ready for Render deployment"
git push origin main --force
echo Done! Check your GitHub repository.
pause
