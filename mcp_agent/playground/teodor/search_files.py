import os
import json
import re
import glob
from pathlib import Path

def find_openbridge_components(project_root):
    """
    Find OpenBridge components in the node_modules directory.
    
    Args:
        project_root: Path to the project root directory
    
    Returns:
        A dictionary containing component information from different sources
    """
    results = {
        "components": [],
        "package_info": []
    }
    
    # Path to OpenBridge packages in node_modules
    openbridge_base_path = os.path.join(project_root, 'node_modules', '@oicl')
    
    # Check if the package is installed
    if not os.path.exists(openbridge_base_path):
        print(f"OpenBridge packages not found at: {openbridge_base_path}")
        
        # Try to get at least some information from package-lock.json
        package_lock_path = os.path.join(project_root, 'package-lock.json')
        if os.path.exists(package_lock_path):
            with open(package_lock_path, 'r') as f:
                package_lock = json.load(f)
                
                # Extract package information
                for pkg_name, pkg_info in package_lock.get('packages', {}).items():
                    if '@oicl/openbridge' in pkg_name:
                        results["package_info"].append({
                            "package": pkg_name,
                            "version": pkg_info.get("version", "unknown")
                        })
        
        return results
    
    # Look for component files
    component_paths = []
    component_paths += glob.glob(os.path.join(openbridge_base_path, 'openbridge-webcomponents', '**', '*.js'), recursive=True)
    component_paths += glob.glob(os.path.join(openbridge_base_path, 'openbridge-webcomponents', '**', '*.ts'), recursive=True)
    component_paths += glob.glob(os.path.join(openbridge_base_path, 'openbridge-webcomponents-react', '**', '*.js'), recursive=True)
    component_paths += glob.glob(os.path.join(openbridge_base_path, 'openbridge-webcomponents-react', '**', '*.ts'), recursive=True)
    
    # Process each file
    for file_path in component_paths:
        if 'node_modules' in file_path and (
            '/components/' in file_path or 
            '/src/' in file_path or 
            '/dist/' in file_path
        ):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Look for component definitions
                    custom_elements = re.findall(r'customElements\.define\([\'"]([^\'"]+-[^\'"]+)[\'"]', content)
                    class_defs = re.findall(r'class\s+(\w+)\s+extends\s+(HTMLElement|LitElement|Component)', content)
                    exports = re.findall(r'export\s+(const|class)\s+(\w+)', content)
                    
                    # Extract component names
                    for elem in custom_elements:
                        results["components"].append({
                            "name": elem,
                            "type": "web-component",
                            "source": os.path.relpath(file_path, project_root)
                        })
                    
                    for class_name, _ in class_defs:
                        results["components"].append({
                            "name": class_name,
                            "type": "component-class",
                            "source": os.path.relpath(file_path, project_root)
                        })
                    
                    for _, export_name in exports:
                        if export_name not in [comp["name"] for comp in results["components"]]:
                            results["components"].append({
                                "name": export_name,
                                "type": "export",
                                "source": os.path.relpath(file_path, project_root)
                            })
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
    
    # Check for package.json files to get metadata
    for package_name in ['openbridge-webcomponents', 'openbridge-webcomponents-react']:
        package_json_path = os.path.join(openbridge_base_path, package_name, 'package.json')
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results["package_info"].append({
                        "name": data.get("name", package_name),
                        "version": data.get("version", "unknown"),
                        "description": data.get("description", "")
                    })
            except Exception as e:
                print(f"Error reading package.json {package_json_path}: {e}")
    
    return results

def format_component_names_for_llm(results):
    """
    Format the component data for use as LLM context.
    """
    component_names = [comp["name"] for comp in results["components"]]
    component_names = list(set(component_names))  # Remove duplicates
    component_names.sort()
    
    output = "# OpenBridge Components\n\n"
    
    # Add package info
    if results["package_info"]:
        output += "## Package Information\n"
        for pkg in results["package_info"]:
            output += f"- {pkg.get('name', 'Unknown')}: v{pkg.get('version', 'unknown')}\n"
            if pkg.get('description'):
                output += f"  Description: {pkg['description']}\n"
        output += "\n"
    
    # Add component list
    output += "## Component Names\n"
    for name in component_names:
        output += f"- {name}\n"
    
    return output, component_names

if __name__ == "__main__":
    project_root = "."  # Default to current directory
    results = find_openbridge_components(project_root)
    
    formatted_output, component_names = format_component_names_for_llm(results)
    print(formatted_output)
    
    # Save to file for later use with LLM
    with open("openbridge_components.txt", "w") as f:
        f.write(formatted_output)
    
    print(f"\nFound {len(component_names)} unique component names.")
    print(f"Component list saved to openbridge_components.txt")