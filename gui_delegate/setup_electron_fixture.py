"""Recreate the isolated Electron test dependency from the reviewed, exact lock."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

BASE=Path(__file__).resolve().parent/'fixtures/electron'
INSTALL_SHA='3b9e0c3c9070edbdb732dc05ed23c6f1c6b7a404bd623033a2f0b71052534e93'
CHECKSUM_SHA='780c9ea6ee5299d4e82f0ffb4b59e823cff2b9dea7c4eb0a43d725a4158ec6cf'
EXE_SHA='c2d88408954d7b62cba8a4d5dae8d02c05b41936507b4370caf17b6ecc183c37'

def main():
    if sys.platform!='win32':raise SystemExit('Fixture installer verified only for Windows x64.')
    node=shutil.which('node');npm=shutil.which('npm.cmd')
    if not node or not npm:raise SystemExit('Existing Node/npm installation required.')
    npm_cli=Path(npm).parent/'node_modules/npm/bin/npm-cli.js'
    if not npm_cli.is_file():raise SystemExit('Cannot identify npm CLI safely.')
    lock=json.loads((BASE/'package-lock.json').read_text('utf-8'))
    for name,pkg in lock['packages'].items():
        if name and (not pkg.get('resolved','').startswith('https://registry.npmjs.org/') or not pkg.get('integrity')):
            raise SystemExit('Unverified dependency source in lock.')
    env={k:v for k,v in os.environ.items() if 'electron' not in k.lower() and k.lower() not in ('npm_config_platform','npm_config_arch','force_no_cache')}
    env.update(ELECTRON_MIRROR='https://github.com/electron/electron/releases/download/',ELECTRON_INSTALL_PLATFORM='win32',ELECTRON_INSTALL_ARCH='x64')
    exe=BASE/'node_modules/electron/dist/electron.exe'
    if not (exe.is_file() and hashlib.sha256(exe.read_bytes()).hexdigest()==EXE_SHA):
        # No remote lifecycle scripts. Execute only the reviewed local installer below.
        subprocess.run([node,str(npm_cli),'ci','--ignore-scripts','--no-audit','--no-fund','--registry=https://registry.npmjs.org'],cwd=BASE,env=env,check=True)
        for name,expected in [('install.js',INSTALL_SHA),('checksums.json',CHECKSUM_SHA)]:
            if hashlib.sha256((BASE/'node_modules/electron'/name).read_bytes()).hexdigest()!=expected:
                raise SystemExit('Reviewed Electron installer/checksum changed; review required.')
        subprocess.run([node,str(BASE/'node_modules/electron/install.js')],cwd=BASE,env=env,check=True)
    if hashlib.sha256(exe.read_bytes()).hexdigest()!=EXE_SHA:raise SystemExit('Electron binary hash mismatch.')
    print(json.dumps({'status':'PASS','version':'44.4.4','binary_sha256':EXE_SHA,'purpose':'isolated synthetic test only'}))

if __name__=='__main__':main()
