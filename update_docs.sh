#!/bin/bash

# Use nix-shell to provide tree command temporarily
if ! command -v tree &> /dev/null; then
    echo "tree command not found, using nix-shell to provide it temporarily"
    nix-shell -p tree --run "$0"
    exit 0
fi

# Remove all files in the output/ folder
rm -rf output/*

# Remove all Python bytecode files and __pycache__ directories
find . -type d -name "__pycache__" -print0 | xargs -0 rm -rf

# Generate tree view of the project directory, excluding tools and .venv
tree -I "tools|.venv" > ./tree.txt

# Extract code structure
python tools/extract_symbols/extract_symbols.py --markdown --output ./code-structure.md src/k3s_deploy_cli/

# Create a backup
cp /home/bas/dev/python/k3s_deploy/docs/start-prompt.md /home/bas/dev/python/k3s_deploy/docs/start-prompt.md.backup

# Get the content up to the structure tag (not including)
grep -n "<structure>" /home/bas/dev/python/k3s_deploy/docs/start-prompt.md > /tmp/line_numbers.txt
FIRST_STRUCTURE_LINE=$(head -1 /tmp/line_numbers.txt | cut -d':' -f1)
STRUCTURE_LINE=$(grep -n "</structure>" /home/bas/dev/python/k3s_deploy/docs/start-prompt.md | head -1 | cut -d':' -f1)
SYMBOLS_LINE=$(grep -n "<symbols>" /home/bas/dev/python/k3s_deploy/docs/start-prompt.md | head -1 | cut -d':' -f1)
SYMBOLS_END_LINE=$(grep -n "</symbols>" /home/bas/dev/python/k3s_deploy/docs/start-prompt.md | head -1 | cut -d':' -f1)

# Create new file with correct structure
head -n $((FIRST_STRUCTURE_LINE - 1)) /home/bas/dev/python/k3s_deploy/docs/start-prompt.md > /home/bas/dev/python/k3s_deploy/temp.md
echo "<structure>" >> /home/bas/dev/python/k3s_deploy/temp.md
cat /home/bas/dev/python/k3s_deploy/tree.txt >> /home/bas/dev/python/k3s_deploy/temp.md
echo "</structure>" >> /home/bas/dev/python/k3s_deploy/temp.md

# Get the content between </structure> and <symbols>
sed -n "$((STRUCTURE_LINE + 1)),$((SYMBOLS_LINE - 1))p" /home/bas/dev/python/k3s_deploy/docs/start-prompt.md >> /home/bas/dev/python/k3s_deploy/temp.md

echo "<symbols>" >> /home/bas/dev/python/k3s_deploy/temp.md
cat /home/bas/dev/python/k3s_deploy/code-structure.md >> /home/bas/dev/python/k3s_deploy/temp.md
echo "</symbols>" >> /home/bas/dev/python/k3s_deploy/temp.md

# Get everything after </symbols>
tail -n +$((SYMBOLS_END_LINE + 1)) /home/bas/dev/python/k3s_deploy/docs/start-prompt.md >> /home/bas/dev/python/k3s_deploy/temp.md

# Replace the original file
mv /home/bas/dev/python/k3s_deploy/temp.md /home/bas/dev/python/k3s_deploy/docs/start-prompt.md

# Clean up temporary files
rm /home/bas/dev/python/k3s_deploy/tree.txt
rm /home/bas/dev/python/k3s_deploy/code-structure.md
rm -f /tmp/line_numbers.txt

echo "Documentation updated in docs/start-prompt.md"
