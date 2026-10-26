import re

with open('app/templates/print_menu.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'menu\[(\d+)\]\.items', r'menu[\1]["items"]', text)

with open('app/templates/print_menu.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('[+] Da sua thanh menu[i]["items"] thanh cong!')
