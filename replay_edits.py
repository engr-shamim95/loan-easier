import json

transcript_path = r'C:\Users\Developer Shamim\.gemini\antigravity\brain\8dcb4466-298b-4858-b104-12b82f3eb3c5\.system_generated\logs\transcript_full.jsonl'

def apply_replacements(filename, file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if 'tool_calls' in data:
                for tc in data['tool_calls']:
                    if tc.get('name') == 'replace_file_content':
                        args = tc.get('args', {})
                        tf = args.get('TargetFile', '')
                        if filename in tf:
                            target = args.get('TargetContent', '')
                            replacement = args.get('ReplacementContent', '')
                            if target in content:
                                content = content.replace(target, replacement)
                                print(f"Successfully applied replacement for {filename}")
                            else:
                                print(f"WARNING: Target not found for {filename}")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

apply_replacements('styles.css', r'I:\Loan Easier\src\static\css\styles.css')
apply_replacements('app.js', r'I:\Loan Easier\src\static\js\app.js')
