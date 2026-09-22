#!/bin/bash

# Meraki MCP Server - Installation Script
# This script automates the setup process

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Meraki MCP Server - Installation Script               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        print_success "Python $PYTHON_VERSION found"
        PYTHON_CMD="python3"
    else
        print_error "Python 3.10 or higher required. Found: $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.10 or higher."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "server.py" ]; then
    print_error "server.py not found. Please run this script from the meraki-mcp-server directory."
    exit 1
fi

print_success "In correct directory"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists. Skipping..."
else
    $PYTHON_CMD -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate || source venv/Scripts/activate
print_success "Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip --quiet
print_success "Pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -e . --quiet
print_success "Dependencies installed"

# Check for .env file
echo ""
echo "Checking for .env file..."
if [ -f ".env" ]; then
    print_success ".env file found"
    
    # Check if API key is set
    if grep -q "MERAKI_API_KEY=your_meraki_api_key_here" .env; then
        print_warning ".env file exists but API key not configured"
        NEED_API_KEY=true
    else
        print_success "API key configured"
        NEED_API_KEY=false
    fi
else
    print_warning ".env file not found. Creating from template..."
    cp .env.example .env
    print_success ".env file created"
    NEED_API_KEY=true
fi

# Prompt for API key if needed
if [ "$NEED_API_KEY" = true ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "API Key Configuration"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "To get your Meraki API key:"
    echo "  1. Log into https://dashboard.meraki.com"
    echo "  2. Go to Organization > Settings"
    echo "  3. Scroll to 'Dashboard API access'"
    echo "  4. Generate and copy your API key"
    echo ""
    read -p "Enter your Meraki API key (or press Enter to skip): " API_KEY
    
    if [ ! -z "$API_KEY" ]; then
        sed -i.bak "s/your_meraki_api_key_here/$API_KEY/" .env
        rm -f .env.bak
        print_success "API key configured in .env file"
    else
        print_warning "API key not configured. You'll need to edit .env manually."
    fi
fi

# Detect MCP client
echo ""
echo "════════════════════════════════════════════════════════════"
echo "MCP Client Detection"
echo "════════════════════════════════════════════════════════════"
echo ""

CLAUDE_CONFIG=""
CLINE_DETECTED=false

# Check for Claude Desktop (macOS)
if [ -d "$HOME/Library/Application Support/Claude" ]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    print_info "Claude Desktop detected (macOS)"
# Check for Claude Desktop (Windows/WSL)
elif [ -d "$APPDATA/Claude" ]; then
    CLAUDE_CONFIG="$APPDATA/Claude/claude_desktop_config.json"
    print_info "Claude Desktop detected (Windows)"
fi

# Check for Cline (VS Code)
if command -v code &> /dev/null; then
    print_info "VS Code detected (Cline may be available)"
    CLINE_DETECTED=true
fi

# Offer to configure
if [ ! -z "$CLAUDE_CONFIG" ] || [ "$CLINE_DETECTED" = true ]; then
    echo ""
    read -p "Would you like to see the configuration instructions? (y/n): " SHOW_CONFIG
    
    if [ "$SHOW_CONFIG" = "y" ] || [ "$SHOW_CONFIG" = "Y" ]; then
        echo ""
        echo "════════════════════════════════════════════════════════════"
        echo "Configuration Instructions"
        echo "════════════════════════════════════════════════════════════"
        
        if [ ! -z "$CLAUDE_CONFIG" ]; then
            echo ""
            echo "For Claude Desktop, add this to:"
            echo "  $CLAUDE_CONFIG"
            echo ""
            echo "{"
            echo "  \"mcpServers\": {"
            echo "    \"meraki-assistant\": {"
            echo "      \"command\": \"$(which python3)\","
            echo "      \"args\": [\"$(pwd)/server.py\"],"
            echo "      \"env\": {"
            echo "        \"MERAKI_API_KEY\": \"your_api_key_here\""
            echo "      }"
            echo "    }"
            echo "  }"
            echo "}"
        fi
        
        if [ "$CLINE_DETECTED" = true ]; then
            echo ""
            echo "For Cline (VS Code), add to your MCP settings:"
            echo ""
            echo "{"
            echo "  \"meraki-assistant\": {"
            echo "    \"command\": \"$(which python3)\","
            echo "    \"args\": [\"$(pwd)/server.py\"],"
            echo "    \"env\": {"
            echo "      \"MERAKI_API_KEY\": \"\${env:MERAKI_API_KEY}\""
            echo "    }"
            echo "  }"
            echo "}"
        fi
    fi
else
    print_warning "No MCP client detected. See QUICKSTART.md for configuration."
fi

# Run tests
echo ""
echo "════════════════════════════════════════════════════════════"
read -p "Would you like to run the test suite? (y/n): " RUN_TESTS

if [ "$RUN_TESTS" = "y" ] || [ "$RUN_TESTS" = "Y" ]; then
    echo ""
    echo "Running tests..."
    if pytest tests/ -v; then
        print_success "All tests passed"
    else
        print_warning "Some tests failed. This may be expected if API key is not configured."
    fi
fi

# Final summary
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Installation Complete!                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_success "Meraki MCP Server is ready to use!"
echo ""
echo "Next steps:"
echo "  1. Ensure your API key is configured (check .env file)"
echo "  2. Configure your MCP client (see above or QUICKSTART.md)"
echo "  3. Restart your MCP client"
echo "  4. Try: 'Show me my Meraki organizations'"
echo ""
echo "Documentation:"
echo "  • README.md - Full documentation"
echo "  • QUICKSTART.md - Quick setup guide"
echo "  • WORKFLOWS.md - Agentic workflows"
echo "  • ARCHITECTURE.md - Technical details"
echo "  • examples/ - Example scripts"
echo ""
echo "To test manually:"
echo "  source venv/bin/activate"
echo "  python examples/agentic_demo.py"
echo ""
print_success "Happy networking! 🚀"
