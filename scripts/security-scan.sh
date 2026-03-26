#!/bin/bash
# Security scan script for TriStar project
# Runs before PR creation to catch vulnerabilities

set -e

echo "🔒 Running security scan..."

# Frontend security (npm audit)
if [ -f "package.json" ]; then
    echo "📦 Checking frontend dependencies..."
    npm audit --audit-level=moderate || {
        echo "❌ Frontend security vulnerabilities found"
        exit 1
    }
    echo "✅ Frontend dependencies are secure"
fi

# Backend security (pip-audit)
if [ -f "requirements.txt" ]; then
    echo "🐍 Checking backend dependencies..."
    if command -v pip-audit &> /dev/null; then
        pip-audit || {
            echo "❌ Backend security vulnerabilities found"
            exit 1
        }
    else
        echo "⚠️  pip-audit not installed, skipping Python security check"
        echo "   Install with: pip install pip-audit"
    fi
    echo "✅ Backend dependencies are secure"
fi

# Check for hardcoded secrets
echo "🔍 Scanning for hardcoded secrets..."
if command -v grep &> /dev/null; then
    # Check for common secret patterns
    if grep -r -E "(sk-ant-|AKIA|ghp_|gho_|password\s*=\s*['\"]|api_key\s*=\s*['\"])" \
       --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" \
       --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=venv \
       src/ 2>/dev/null; then
        echo "❌ Potential hardcoded secrets found in source code"
        exit 1
    fi
fi
echo "✅ No hardcoded secrets detected"

# Check for .env files in git
if git ls-files | grep -E "\.env$|\.env\." &> /dev/null; then
    echo "❌ .env files found in git! Remove them immediately:"
    git ls-files | grep -E "\.env$|\.env\."
    exit 1
fi
echo "✅ No .env files in git"

echo "✅ Security scan passed!"
exit 0
