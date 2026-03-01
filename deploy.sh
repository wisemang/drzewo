#!/bin/bash

# Configuration
SSH_HOST="drzewo-user"
REMOTE_DIR="/home/drzewo/webapp/drzewo"
APP_NAME="drzewo"

# Deploy files (excluding .env)
echo "📦 Deploying files..."
scp -r static templates scripts *.py requirements.txt Makefile drzewo.sql README.md $SSH_HOST:$REMOTE_DIR

# If this is first deployment, copy .env template
echo "🔧 Checking environment configuration..."
ssh $SSH_HOST << 'EOF'
    cd /home/drzewo/webapp/drzewo
    if [ ! -f .env ]; then
        echo "Creating .env file..."
        cat > .env << 'ENVFILE'
DRZEWO_DB=drzewo
DRZEWO_DB_USER=your_db_user
DRZEWO_DB_PW=your_db_password
DRZEWO_DB_HOST=localhost
DRZEWO_DB_PORT=5432
ENVFILE
        echo "⚠️  Please edit .env file with correct values"
        exit 1
    fi

    # Install any new requirements
    source venv/bin/activate
    pip install -r requirements.txt
    pip install python-dotenv  # Make sure this is installed

    # Restart Gunicorn
    sudo systemctl restart gunicorn
EOF

echo "✅ Deployment complete!" 
