import glob
import os

folder_path = r'F:\EMAK_ODOO\odoo_base\Emak_Odoo\dan_code\dynamic_accounts_report\static\src\xml'

for file_path in glob.glob(os.path.join(folder_path, '*.xml')):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'o_action o_view_controller' not in content:
        content = content.replace('<div class="container">', '<div class="o_action o_view_controller">\n            <div class="o_content">\n                <div class="container">', 1)
        
        parts = content.rsplit('</t>', 1)
        if len(parts) == 2:
            content = parts[0] + '            </div>\n        </div>\n    </t>' + parts[1]
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed {file_path}')
