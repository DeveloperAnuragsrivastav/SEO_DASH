import os, re, json

def scan_dir(d):
    data = {}
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(('.tsx', '.ts')):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    
                    # API calls
                    api_calls = re.findall(r'api\.(get|post|put|delete)\([^\)]+\)', content)
                    
                    # State
                    use_states = re.findall(r'useState(<[^>]+>)?\([^)]*\)', content)
                    use_contexts = re.findall(r'useContext\([^)]*\)', content)
                    
                    # Components (basic heuristic: <CapitalizedName ...)
                    components = list(set(re.findall(r'<([A-Z][a-zA-Z0-9]+)', content)))
                    
                    if api_calls or use_states or use_contexts or components:
                        data[path.replace('frontend/src/', '')] = {
                            'api_calls': list(set(api_calls)),
                            'states': len(use_states),
                            'contexts': list(set(use_contexts)),
                            'components': components
                        }
    return data

print(json.dumps(scan_dir('frontend/src/pages'), indent=2))
print("---COMPONENTS---")
print(json.dumps(scan_dir('frontend/src/components'), indent=2))
