"""Install the cattle models and a foreground app in the MaixCAM launcher."""

import argparse
import base64
import configparser
from datetime import datetime
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import shlex


ROOT = Path(__file__).resolve().parents[1]
APP_ID = 'shumu_ywh'
APP_NAME = '\u6768\u6587\u660a-\u6570\u7267\u589e\u6548'
REMOTE_APP = '/maixapp/apps/' + APP_ID
REGISTRY = '/maixapp/apps/app.info'
EXPECTED_UUID = '22a051af-0675-4d62-bed7-98e0dde8dfc0'


def register_app(original):
    registry = configparser.ConfigParser(interpolation=None)
    registry.optionxform = str
    registry.read_string(original)
    registry[APP_ID] = {
        'name': APP_NAME, 'name[zh]': APP_NAME, 'version': '1.1.0',
        'icon': 'icon.png', 'author': '\u6768\u6587\u660a',
        'desc': 'Cattle detection and appearance research',
        'desc[zh]': '\u725b\u53ea\u68c0\u6d4b\u4e0e\u5916\u89c2\u7814\u7a76', 'exec': 'main.py',
    }
    output = io.StringIO()
    registry.write(output)
    return output.getvalue()


def model_pair(model):
    model = Path(model)
    descriptor = configparser.ConfigParser(interpolation=None)
    descriptor.read(model, encoding='utf-8')
    filename = descriptor['basic']['model'].strip()
    if Path(filename).name != filename or '/' in filename or '\\' in filename or not filename.endswith('.cvimodel'):
        raise ValueError('A MUD model must reference a CVIMODEL in the same directory')
    binary = model.with_name(filename)
    if not binary.is_file():
        raise FileNotFoundError(binary)
    return model, binary


def package_files(research_model_dir=None):
    hardware = ROOT / '\u786c\u4ef6\u4ee3\u7801' / 'MaixCam\u8282\u70b9'
    source = hardware / 'launcher_app'
    files = {path.relative_to(source).as_posix(): path.read_bytes()
             for path in source.rglob('*') if path.is_file() and path.suffix in ('.py', '.yaml', '.png')}
    for required in ('main.py', 'app.yaml', 'icon.png'):
        if required not in files:
            raise FileNotFoundError(source / required)
    files['vision_node.py'] = (hardware / 'main.py').read_bytes()
    research_dir = Path(research_model_dir) if research_model_dir else ROOT / 'vision-training-data/maixcam-cascade-20261028'
    conversion = json.loads((research_dir / 'conversion_result.json').read_text(encoding='utf-8'))
    if conversion['status'] != 'converted_research_only' or conversion['scope'] != 'research_only':
        raise ValueError('A reviewed research conversion result is required')
    models = [hardware / 'models/cattle_yolov8.mud', research_dir / 'cattle_research.mud']
    trusted = ['1d547f377181c7748730f1e1fcfe6e846b772a6976632566b36b97d068c6730e',
               conversion['cvimodel_sha256']]
    for model, expected_hash in zip(models, trusted):
        pair = model_pair(model)
        if hashlib.sha256(pair[1].read_bytes()).hexdigest() != expected_hash:
            raise ValueError('Model differs from the reviewed artifact: ' + pair[1].name)
        for path in pair:
            content = path.read_bytes()
            files['models/' + path.name] = content
    config = json.loads((hardware / 'config.json').read_text(encoding='utf-8-sig'))
    config.update(app_name=APP_NAME, default_mode='cow_detection', display_enabled=True,
                  cow_model_path='models/cattle_yolov8.mud', research_model_path='models/cattle_research.mud',
                  classifier_softmax=True, classifier_image_size=224,
                  backend_url='', backend_api_key='', mqtt_host='', mqtt_user='', mqtt_pass='')
    if conversion.get('input_geometry') != 'cow_roi_letterbox':
        raise ValueError('This app requires a classifier trained on letterboxed cow regions')
    thresholds = json.loads((research_dir / 'rejection_thresholds.json').read_text(encoding='utf-8'))
    config.update(default_mode='appearance_research', cascade_enabled=True,
                  cascade_minimum_score=thresholds['minimum_score'],
                  cascade_minimum_margin=thresholds['minimum_margin'],
                  cascade_minimum_side=32, cascade_max_regions=2,
                  research_model_version='cow-roi-20261028', classifier_geometry='cow_roi_letterbox')
    files['config.json'] = (json.dumps(config, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return files


def remote_python(client, source):
    encoded = base64.b64encode(source.encode('utf-8')).decode('ascii')
    command = 'python3 -c ' + shlex.quote("import base64;exec(base64.b64decode('" + encoded + "'))")
    _, stdout, stderr = client.exec_command(command, timeout=90)
    output = stdout.read().decode('utf-8', 'replace')
    error = stderr.read().decode('utf-8', 'replace')
    if stdout.channel.recv_exit_status() != 0:
        raise RuntimeError(error or output or 'Camera operation failed')
    return output


def install(client, files, evidence):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    staging = '/root/shumu-ywh-staging-' + stamp
    backup = '/root/shumu-ywh-install-backup-' + stamp
    sftp = client.open_sftp()
    try:
        with sftp.open(REGISTRY, 'rb') as stream:
            original = stream.read()
        (evidence / 'app.info.before').write_bytes(original)
        updated = register_app(original.decode('utf-8')).encode('utf-8')
        remote_python(client, 'import os\nassert os.geteuid()==0\n'
                      + "import subprocess\nassert " + repr(EXPECTED_UUID)
                      + " in subprocess.check_output(['blkid','/dev/mmcblk0p2']).decode()\n"
                      + 'os.mkdir(' + repr(staging) + ')\n')
        created = {staging}
        hashes = {}
        for name, content in sorted(files.items()):
            target = staging + '/' + name
            parent = str(Path(name).parent).replace('\\', '/')
            if parent != '.':
                current = staging
                for part in parent.split('/'):
                    current += '/' + part
                    if current not in created:
                        sftp.mkdir(current)
                        created.add(current)
            with sftp.open(target, 'wb') as stream:
                stream.write(content)
            sftp.chmod(target, 0o644)
            hashes[name] = hashlib.sha256(content).hexdigest()
        payload = {'staging': staging, 'backup': backup, 'target': REMOTE_APP,
                   'registry': REGISTRY, 'original_sha256': hashlib.sha256(original).hexdigest(),
                   'updated': base64.b64encode(updated).decode('ascii'), 'hashes': hashes}
        transaction = '''
import base64,hashlib,json,os
p=json.loads(PAYLOAD)
digest=lambda data:hashlib.sha256(data).hexdigest()
for name,expected in p['hashes'].items():
    with open(p['staging']+'/'+name,'rb') as f:
        if digest(f.read())!=expected: raise ValueError('Uploaded file hash mismatch: '+name)
for entry in os.listdir('/proc'):
    if entry.isdigit():
        try:
            with open('/proc/'+entry+'/cmdline','rb') as f: args=f.read().split(b'\\0')
            if (p['target']+'/main.py').encode() in args: raise RuntimeError('Close the installed app before updating it')
        except (FileNotFoundError,ProcessLookupError,PermissionError): pass
with open(p['registry'],'rb') as f: original=f.read()
if digest(original)!=p['original_sha256']: raise RuntimeError('Launcher registry changed during upload')
os.mkdir(p['backup'])
with open(p['backup']+'/app.info','wb') as f: f.write(original)
updated=base64.b64decode(p['updated'])
had_app=os.path.exists(p['target'])
activated=False
try:
    if had_app: os.rename(p['target'],p['backup']+'/app')
    os.rename(p['staging'],p['target']); activated=True
    temporary=p['registry']+'.shumu-new'
    with open(temporary,'wb') as f:
        f.write(updated); f.flush(); os.fsync(f.fileno())
    os.replace(temporary,p['registry'])
    with open(p['registry'],'rb') as f:
        if f.read()!=updated: raise IOError('Launcher registry readback mismatch')
    os.sync()
except BaseException:
    if activated: os.rename(p['target'],p['staging'])
    if had_app and os.path.exists(p['backup']+'/app'): os.rename(p['backup']+'/app',p['target'])
    with open(p['registry'],'rb') as f: current=f.read()
    if current==updated:
        with open(p['registry']+'.shumu-rollback','wb') as f:
            f.write(original); f.flush(); os.fsync(f.fileno())
        os.replace(p['registry']+'.shumu-rollback',p['registry'])
    os.sync()
    raise
print(json.dumps({'status':'installed','app_id':'shumu_ywh','app_path':p['target'],'backup':p['backup'],
                  'files_verified':len(p['hashes']),'hashes':p['hashes']}))
'''.replace('PAYLOAD', repr(json.dumps(payload)))
        result = json.loads(remote_python(client, transaction))
        result['display_name'] = APP_NAME
        (evidence / 'installation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        sftp.close()


def main():
    import paramiko
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='10.139.183.1')
    parser.add_argument('--user', default='root')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--research-model-dir', type=Path)
    args = parser.parse_args()
    files = package_files(args.research_model_dir)
    args.output.mkdir(parents=True, exist_ok=False)
    password = os.environ.get('SHUMU_MAIX_PASSWORD') or getpass.getpass('MaixCAM SSH password: ')
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(args.host, username=args.user, password=password, timeout=10,
                       auth_timeout=10, allow_agent=False, look_for_keys=False)
        print(json.dumps(install(client, files, args.output), ensure_ascii=True, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    main()
