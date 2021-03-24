import os
import subprocess

REQUIREMENTS = ('Jinja2', 'motor', 'aiohttp', 'dnspython')

pipfreeze = subprocess.check_output('pip3 freeze', shell=True, universal_newlines=True)

for req in REQUIREMENTS:
	req_tmp = req
	if '==' not in req:
		req_tmp = req + '=='
	if req_tmp.lower() not in pipfreeze.lower():
		os.system(f'pip3 install {req}')

print('ready to start')