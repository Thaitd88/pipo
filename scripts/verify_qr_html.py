import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# S2-01
html_s2 = urllib.request.urlopen('https://pipogarden.com/c/2122f942736db5ed').read().decode('utf-8')
m_branch = re.search(r'branchType:\s*"([^"]+)"', html_s2)
print("S2-01 branchType in HTML:", m_branch.group(1) if m_branch else "NOT FOUND")
m_area = re.search(r'area:\s*"([^"]+)"', html_s2)
print("S2-01 area in HTML:", m_area.group(1) if m_area else "NOT FOUND")

# PK-01
html_pk = urllib.request.urlopen('https://pipogarden.com/c/e115723c2cba93cc').read().decode('utf-8')
m_pk_branch = re.search(r'branchType:\s*"([^"]+)"', html_pk)
print("PK-01 branchType in HTML:", m_pk_branch.group(1) if m_pk_branch else "NOT FOUND")
