#!/usr/bin/env python3

import ast
import argparse
import inspect
from pathlib import Path
import os

class SymbolExtractor(ast.NodeVisitor):
    """
    Visits AST nodes to extract symbol definitions (classes, functions).
    """
    def __init__(self, filepath):
        self.filepath = filepath
        self.symbols = []
        self.source_code = None
        self.class_stack = []  # Stack to track current class context

    def _add_symbol(self, node, symbol_type):
        symbol = {
            'name': node.name,
            'type': symbol_type,
            'file': str(self.filepath.resolve()), # Use absolute path
            'line': node.lineno,
            'col': node.col_offset,
            'parent_class': self.class_stack[-1] if self.class_stack else None  # Track parent class
        }
        
        # Extract signature if it's a function or async function
        if symbol_type in ('function', 'async function') and self.source_code:
            try:
                # Get the source lines for this function
                lines = self.source_code.splitlines()
                # Find the function header (could span multiple lines)
                func_header = []
                in_header = True
                i = node.lineno - 1  # Python uses 1-indexed lines, list is 0-indexed
                
                # Extract the function definition including parameters
                while i < len(lines) and in_header:
                    line = lines[i].lstrip()
                    func_header.append(line)
                    # Check if the line contains the end of the function header
                    if line.endswith(':') and not line.endswith('\\:'):
                        in_header = False
                    i += 1
                
                # Join the function header lines and remove the trailing colon
                signature = ' '.join(func_header).rstrip(':')
                symbol['signature'] = signature
            except Exception:
                symbol['signature'] = f"def {node.name}(...)"
        
        self.symbols.append(symbol)

    def visit_ClassDef(self, node):
        self._add_symbol(node, 'class')
        # Push this class onto the stack before visiting its contents
        self.class_stack.append(node.name)
        self.generic_visit(node)  # Visit methods etc. inside the class
        # Pop the class from the stack after visiting its contents
        self.class_stack.pop()

    def visit_FunctionDef(self, node):
        self._add_symbol(node, 'function')
        self.generic_visit(node) # Visit nested functions/classes if any

    def visit_AsyncFunctionDef(self, node):
        self._add_symbol(node, 'async function')
        self.generic_visit(node) # Visit nested functions/classes if any

    # --- Optional: Add other symbols ---
    # def visit_Assign(self, node):
    #     # This finds ALL assignments (variables, constants).
    #     # Might be too noisy. Filter targets if needed.
    #     for target in node.targets:
    #         if isinstance(target, ast.Name):
    #              self.symbols.append({
    #                  'name': target.id,
    #                  'type': 'variable', # Or constant? Hard to tell statically
    #                  'file': str(self.filepath.resolve()),
    #                  'line': node.lineno,
    #                  'col': node.col_offset
    #              })
    #     self.generic_visit(node)

    # def visit_AnnAssign(self, node):
    #      # Handles type-annotated assignments like x: int = 5
    #     if isinstance(node.target, ast.Name):
    #          self.symbols.append({
    #              'name': node.target.id,
    #              'type': 'variable (annotated)',
    #              'file': str(self.filepath.resolve()),
    #              'line': node.lineno,
    #              'col': node.col_offset
    #          })
    #     self.generic_visit(node)


def find_symbols_in_project(project_dir, exclusions):
    """
    Recursively finds Python files and extracts symbols, excluding specified directories and files.
    """
    project_path = Path(project_dir)
    all_symbols = []

    for py_file in project_path.rglob('*.py'):
        # Convert to string for easier comparison
        file_str = str(py_file)
        
        # Skip if this file should be excluded
        if any(excl in file_str for excl in exclusions):
            print(f"Skipping excluded path: {py_file}")
            continue

        print(f"Processing: {py_file}")
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
            tree = ast.parse(source_code, filename=str(py_file))
            extractor = SymbolExtractor(py_file)
            extractor.source_code = source_code
            extractor.visit(tree)
            all_symbols.extend(extractor.symbols)
        except SyntaxError as e:
            print(f"  Warning: Skipping {py_file} due to SyntaxError: {e}")
        except Exception as e:
            print(f"  Warning: Skipping {py_file} due to error: {e}")

    return all_symbols

def generate_markdown_output(symbols):
    """
    Generate nicely formatted markdown output from the extracted symbols with proper nesting.
    """
    if not symbols:
        return "# Symbol Extraction Results\n\nNo symbols found."
    
    # Group symbols by file
    files = {}
    for symbol in symbols:
        file_path = symbol['file']
        if file_path not in files:
            files[file_path] = []
        files[file_path].append(symbol)
    
    markdown = ["# Symbol Extraction Results\n"]
    
    # Process each file
    for file_path, file_symbols in sorted(files.items()):
        # Use relative path if possible for cleaner output
        try:
            rel_path = os.path.relpath(file_path)
            display_path = rel_path if not rel_path.startswith('..') else file_path
        except:
            display_path = file_path
            
        markdown.append(f"\n## {display_path}\n")
        
        # Sort symbols by line number
        file_symbols.sort(key=lambda s: s['line'])
        
        # First process classes
        classes = {}
        top_level_functions = []
        
        # Separate classes and top-level functions
        for symbol in file_symbols:
            if symbol['type'] == 'class':
                classes[symbol['name']] = {
                    'symbol': symbol,
                    'methods': []
                }
            elif symbol['type'] in ('function', 'async function') and not symbol.get('parent_class'):
                top_level_functions.append(symbol)
        
        # Add methods to their respective classes
        for symbol in file_symbols:
            if symbol['type'] in ('function', 'async function') and symbol.get('parent_class'):
                if symbol['parent_class'] in classes:
                    classes[symbol['parent_class']]['methods'].append(symbol)
        
        # Output classes with their methods
        for class_name, class_data in sorted(classes.items()):
            class_symbol = class_data['symbol']
            markdown.append(f"### 🔷 Class: `{class_name}`")
            markdown.append(f"- **Line:** {class_symbol['line']}")
            markdown.append("")
            
            # Add methods under this class
            for method in sorted(class_data['methods'], key=lambda m: m['line']):
                prefix = "🔶" if method['type'] == 'function' else "⚡"
                markdown.append(f"#### {prefix} {method['type'].capitalize()}: `{method['name']}`")
                markdown.append(f"- **Line:** {method['line']}")
                if 'signature' in method:
                    markdown.append("```python")
                    markdown.append(method['signature'])
                    markdown.append("```")
                markdown.append("")
        
        # Output top-level functions
        for func in top_level_functions:
            prefix = "🔶" if func['type'] == 'function' else "⚡"
            markdown.append(f"### {prefix} {func['type'].capitalize()}: `{func['name']}`")
            markdown.append(f"- **Line:** {func['line']}")
            if 'signature' in func:
                markdown.append("```python")
                markdown.append(func['signature'])
                markdown.append("```")
            markdown.append("")
    
    return '\n'.join(markdown)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract symbols (classes, functions) from a Python project.")
    parser.add_argument("project_dir", nargs='?', default='.',
                        help="The root directory of the Python project (default: current directory)")
    parser.add_argument("--exclude", nargs='*', default=[],
                        help="List of directories and/or files to exclude from processing")
    parser.add_argument("--no-signatures", action="store_true", 
                        help="Don't show function signatures")
    parser.add_argument("--markdown", "-m", action="store_true",
                        help="Output in markdown format")
    parser.add_argument("--output", "-o", type=str,
                        help="Output file (default: stdout)")

    args = parser.parse_args()

    symbols = find_symbols_in_project(args.project_dir, args.exclude)

    if args.markdown:
        output = generate_markdown_output(symbols)
    else:
        # Standard text output format
        output_lines = ["--- Found Symbols ---"]
        if symbols:
            # Sort for consistent output (optional)
            symbols.sort(key=lambda s: (s['file'], s['line']))
            for symbol in symbols:
                base_info = f"{symbol['file']}:{symbol['line']}:{symbol['col']} \t {symbol['type']} \t {symbol['name']}"
                if not args.no-signatures and symbol['type'] in ('function', 'async function') and 'signature' in symbol:
                    output_lines.append(f"{base_info}\n    {symbol['signature']}")
                else:
                    output_lines.append(base_info)
        else:
            output_lines.append("No symbols found.")
        output = '\n'.join(output_lines)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
    else:
        print(output)