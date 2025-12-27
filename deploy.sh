#!/bin/bash

# Baron AI Bot - Render Deployment Script
echo "🚀 Baron AI Bot - Render Deployment"
echo "===================================="

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📋 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit: Baron AI Trading Bot"
else
    echo "📋 Git repository already initialized"
fi

# Check if remote exists
if git remote get-url origin &>/dev/null; then
    echo "🔄 Pushing to existing GitHub repository..."
    git add .
    git commit -m "Ready for Render deployment"
    git push origin main
else
    echo "⚠️  No GitHub remote found!"
    echo "Please:"
    echo "1. Create a new repository on GitHub"
    echo "2. Run: git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
    echo "3. Run: git push -u origin main"
    echo ""
    echo "Then deploy on Render using the repository URL"
fi

echo ""
echo "🎯 Next Steps:"
echo "1. Go to https://render.com"
echo "2. Click 'New' → 'Web Service'"
echo "3. Connect your GitHub repository"
echo "4. Configure environment variables (see RENDER_DEPLOYMENT.md)"
echo "5. Deploy!"
echo ""
echo "📚 Documentation:"
echo "- RENDER_DEPLOYMENT.md - Complete deployment guide"
echo "- README.md - Project overview"
echo "- .env.example - Environment variables template"
