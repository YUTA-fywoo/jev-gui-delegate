"""Small tool-facing contract envelope; the full strict schema stays local."""
import json
from pathlib import Path, PureWindowsPath
from .schema import Contract
from .security import Stop

def input_schema():
    # Retain every legacy inline field without repeating the nested DSL to the
    # model. Contract.model_validate remains authoritative for both formats.
    full=Contract.model_json_schema()
    properties={name:{'type':('object' if '$ref' in spec else spec.get('type','object'))}
                for name,spec in full['properties'].items()}
    properties['contract_path']={'type':'string','description':'Preferred: absolute local .json contract path. Use alone. Full schema: gui_delegate/schemas/contract.json; skill references/protocol.md.'}
    return {'type':'object','properties':properties,'additionalProperties':False,
            'anyOf':[{'required':['contract_path'],'maxProperties':1},
                     {'required':full['required'],'not':{'required':['contract_path']}}]}

def load(arguments):
    if not isinstance(arguments,dict):raise Stop('INVALID_TASK_SCHEMA','blocked')
    if 'contract_path' not in arguments:return arguments
    if set(arguments)!={'contract_path'}:raise Stop('CONTRACT_ENVELOPE_MIXED','blocked')
    name=arguments['contract_path']
    if not isinstance(name,str):raise Stop('CONTRACT_PATH_DENIED','blocked')
    p=Path(name);win=PureWindowsPath(name)
    if (not p.is_absolute() or p.suffix.lower()!='.json' or win.drive.startswith('\\\\')
            or ':' in name[2:]):raise Stop('CONTRACT_PATH_DENIED','blocked')
    try:
        for part in (p,*p.parents):
            info=part.lstat()
            if part.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
                raise Stop('CONTRACT_LINK_DENIED','blocked')
        if not p.is_file():raise Stop('CONTRACT_PATH_DENIED','blocked')
        with p.open('rb') as stream:raw=stream.read(1_000_001)
        if len(raw)>1_000_000:raise Stop('CONTRACT_TOO_LARGE','blocked')
        value=json.loads(raw.decode('utf-8-sig'))
    except (OSError,UnicodeError,ValueError):raise Stop('CONTRACT_FILE_INVALID','blocked') from None
    if not isinstance(value,dict):raise Stop('INVALID_TASK_SCHEMA','blocked')
    return value
