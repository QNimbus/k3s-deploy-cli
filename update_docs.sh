#!/bin/bash

# Use nix-shell to provide tree command temporarily
if ! command -v tree &> /dev/null; then
    echo "tree command not found, using nix-shell to provide it temporarily"
    nix-shell -p tree --run "$0"
    exit 0
fi

BASE_DIR="/workspaces/k3s_deploy"

# Remove all files in the output/ folder
rm -rf output/*

# Remove all Python bytecode files and __pycache__ directories
find . -type d -name "__pycache__" -print0 | xargs -0 rm -rf

# Generate tree view of the project directory, excluding tools and .venv
tree -aI "tools|tree.txt|*.backup|*.sample|*.lock|tests|update_docs.sh|.venv|.vscode|.git*|.jj|.devcontainer" > ./tree.txt

# Extract code structure
python tools/extract_symbols/extract_symbols.py --markdown --output ./code-structure.md src/k3s_deploy_cli/

# Create a backup
cp "${BASE_DIR}/docs/start-prompt.md" "${BASE_DIR}/docs/start-prompt.md.backup"

# Get the content up to the structure tag (not including)
grep -n "<structure>" "${BASE_DIR}/docs/start-prompt.md" > /tmp/line_numbers.txt
FIRST_STRUCTURE_LINE=$(head -1 /tmp/line_numbers.txt | cut -d':' -f1)
STRUCTURE_LINE=$(grep -n "</structure>" "${BASE_DIR}/docs/start-prompt.md" | head -1 | cut -d':' -f1)
SYMBOLS_LINE=$(grep -n "<symbols>" "${BASE_DIR}/docs/start-prompt.md" | head -1 | cut -d':' -f1)
SYMBOLS_END_LINE=$(grep -n "</symbols>" "${BASE_DIR}/docs/start-prompt.md" | head -1 | cut -d':' -f1)

# Create new file with correct structure
head -n $((FIRST_STRUCTURE_LINE - 1)) "${BASE_DIR}/docs/start-prompt.md" > "${BASE_DIR}/temp.md"
echo "<structure>" >> "${BASE_DIR}/temp.md"
cat "${BASE_DIR}/tree.txt" >> "${BASE_DIR}/temp.md"
echo "</structure>" >> "${BASE_DIR}/temp.md"

# Get the content between </structure> and <symbols>
sed -n "$((STRUCTURE_LINE + 1)),$((SYMBOLS_LINE - 1))p" "${BASE_DIR}/docs/start-prompt.md" >> "${BASE_DIR}/temp.md"

echo "<symbols>" >> "${BASE_DIR}/temp.md"
cat "${BASE_DIR}/code-structure.md" >> "${BASE_DIR}/temp.md"
echo "</symbols>" >> "${BASE_DIR}/temp.md"

# Get everything after </symbols>
tail -n +$((SYMBOLS_END_LINE + 1)) "${BASE_DIR}/docs/start-prompt.md" >> "${BASE_DIR}/temp.md"

# Replace the original file
mv "${BASE_DIR}/temp.md" "${BASE_DIR}/docs/start-prompt.md"

# Clean up temporary files
rm "${BASE_DIR}/tree.txt"
rm "${BASE_DIR}/code-structure.md"
rm -f /tmp/line_numbers.txt

echo "Documentation updated in docs/start-prompt.md"
