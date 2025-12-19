#!/bin/bash
# Helper script to add a folder from your computer to Archive Brain
# Usage: ./scripts/add-folder.sh /path/to/your/folder [mount_name]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# Check if path was provided
if [ -z "$1" ]; then
    echo -e "${BLUE}Archive Brain - Add Folder${NC}"
    echo ""
    echo "Usage: $0 /path/to/folder [mount_name]"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo ""
    echo "  Linux:"
    echo "    $0 /home/user/documents"
    echo "    $0 ~/notes my-notes"
    echo ""
    echo "  macOS:"
    echo "    $0 /Users/yourname/Documents"
    echo "    $0 ~/Desktop/research"
    echo ""
    echo "  Windows (via WSL):"
    echo "    $0 /mnt/c/Users/YourName/Documents"
    echo "    $0 /mnt/d/Projects my-projects"
    echo ""
    echo -e "${YELLOW}Windows Path Translation:${NC}"
    echo "  C:\\Users\\John\\Documents  →  /mnt/c/Users/John/Documents"
    echo "  D:\\Backup\\Files         →  /mnt/d/Backup/Files"
    echo ""
    echo "The folder will be accessible inside the containers at:"
    echo "  /data/archive/<mount_name>"
    exit 1
fi

# Handle Windows-style paths (convert C:\path to /mnt/c/path)
INPUT_PATH="$1"
if [[ "$INPUT_PATH" =~ ^[A-Za-z]:\\ ]] || [[ "$INPUT_PATH" =~ ^[A-Za-z]:/ ]]; then
    # Extract drive letter and convert
    DRIVE_LETTER=$(echo "${INPUT_PATH:0:1}" | tr '[:upper:]' '[:lower:]')
    REST_OF_PATH="${INPUT_PATH:2}"
    # Convert backslashes to forward slashes
    REST_OF_PATH=$(echo "$REST_OF_PATH" | tr '\\' '/')
    INPUT_PATH="/mnt/$DRIVE_LETTER$REST_OF_PATH"
    echo -e "${YELLOW}Converted Windows path to WSL format:${NC} $INPUT_PATH"
fi

# Resolve the path (handle ~ and relative paths)
HOST_PATH=$(realpath -m "$INPUT_PATH" 2>/dev/null || echo "$INPUT_PATH")

# Check if path exists
if [ ! -d "$HOST_PATH" ]; then
    echo -e "${RED}Error:${NC} Directory does not exist: $HOST_PATH"
    echo ""
    if [[ "$HOST_PATH" == /mnt/* ]]; then
        echo -e "${YELLOW}Tip:${NC} For Windows paths, make sure:"
        echo "  1. The folder exists on your Windows drive"
        echo "  2. You're running this from within WSL (not Windows CMD/PowerShell)"
        echo "  3. The path format is correct: /mnt/c/Users/..."
    fi
    exit 1
fi

# Count files in the directory
FILE_COUNT=$(find "$HOST_PATH" -type f 2>/dev/null | wc -l)

# Get mount name (use folder name if not provided)
if [ -n "$2" ]; then
    MOUNT_NAME="$2"
else
    MOUNT_NAME=$(basename "$HOST_PATH" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
fi

# Sanitize mount name
MOUNT_NAME=$(echo "$MOUNT_NAME" | sed 's/[^a-zA-Z0-9_-]/-/g')

CONTAINER_PATH="/data/archive/$MOUNT_NAME"
VOLUME_LINE="      - $HOST_PATH:$CONTAINER_PATH"

echo -e "${BLUE}Archive Brain - Add Folder${NC}"
echo ""
echo -e "Host path:      ${GREEN}$HOST_PATH${NC}"
echo -e "Container path: ${GREEN}$CONTAINER_PATH${NC}"
echo -e "Mount name:     ${GREEN}$MOUNT_NAME${NC}"
echo -e "Files found:    ${CYAN}$FILE_COUNT${NC}"
echo ""

# Check if docker-compose.yml exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error:${NC} docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi

# Check if this mount already exists
if grep -q "$HOST_PATH:" "$COMPOSE_FILE" 2>/dev/null; then
    echo -e "${YELLOW}Warning:${NC} This path appears to already be mounted in docker-compose.yml"
    read -p "Continue anyway? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        exit 0
    fi
fi

# Create backup
BACKUP_FILE="$COMPOSE_FILE.backup.$(date +%Y%m%d_%H%M%S)"
cp "$COMPOSE_FILE" "$BACKUP_FILE"
echo -e "Created backup: ${YELLOW}$BACKUP_FILE${NC}"

# Add the volume mount to both worker and api services
# This is a bit tricky with sed, so we'll use Python for reliability
python3 << EOF
import re

compose_file = "$COMPOSE_FILE"
volume_line = "$VOLUME_LINE"
mount_name = "$MOUNT_NAME"

with open(compose_file, 'r') as f:
    content = f.read()

# Pattern to find volumes section under worker: and api: services
# We need to add the line after the existing volumes

def add_volume_to_service(content, service_name):
    """Add volume mount to a service's volumes section"""
    # Find the service section
    pattern = rf'(  {service_name}:.*?volumes:\n)((?:      - [^\n]+\n)*)'
    
    def replacer(match):
        service_start = match.group(1)
        existing_volumes = match.group(2)
        return service_start + existing_volumes + volume_line + '\n'
    
    return re.sub(pattern, replacer, content, flags=re.DOTALL)

# Add to worker service
content = add_volume_to_service(content, 'worker')
# Add to api service  
content = add_volume_to_service(content, 'api')

with open(compose_file, 'w') as f:
    f.write(content)

print(f"Added volume mount to worker and api services")
EOF

echo ""
echo -e "${GREEN}✓ Updated docker-compose.yml${NC}"
echo ""

# Ask about restarting
read -p "Restart containers now to apply changes? (Y/n): " restart
if [ "$restart" != "n" ] && [ "$restart" != "N" ]; then
    echo ""
    echo "Restarting containers..."
    cd "$PROJECT_DIR"
    docker compose down
    docker compose --profile prod up -d
    echo ""
    echo -e "${GREEN}✓ Containers restarted${NC}"
fi

echo ""
echo -e "${GREEN}Done!${NC} Your folder is now available at: $CONTAINER_PATH"
echo ""
echo "Next steps:"
echo "  1. Refresh the Setup Wizard page (or go to Settings > Source Folders)"
echo "  2. Select your new folder to include it in indexing"
echo ""
