#!/bin/bash
# AI Cost Optimizer - Installation Script

set -e  # Exit on error

echo "🚀 AI Cost Optimizer - Installation"
echo "===================================="
echo ""

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "❌ Python 3.8+ is required. Current version: $python_version"
    exit 1
fi
echo "✅ Python $python_version detected"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dependencies installed"
echo ""

# Install MCP dependencies
echo "📥 Installing MCP server dependencies..."
pip install -r mcp/requirements.txt -q
echo "✅ MCP dependencies installed"
echo ""

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys"
    echo "   At least one provider API key is required."
    echo ""
else
    echo "ℹ️  .env file already exists"
    echo ""
fi

# Create data directory
if [ ! -d "data" ]; then
    mkdir -p data
    echo "✅ Data directory created"
fi

echo "✨ Installation complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env and add your API keys:"
echo "   nano .env"
echo ""
echo "2. Start the service:"
echo "   python app/main.py"
echo ""
echo "3. Test it works:"
echo "   curl http://localhost:8000/health"
echo ""
echo "4. Configure Claude Desktop (see README.md for details)"
echo ""
echo "💡 Tip: You can also use Docker:"
echo "   docker-compose up --build"
echo ""
