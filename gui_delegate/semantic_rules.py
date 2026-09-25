"""Small auditable intent grammars and exact control aliases, not a general parser.

Rules use trusted step intent and approved observed labels. They cannot grant
authority, create an action, or supply a coordinate/path/value. Unknown wording
falls through to the existing semantic decision policy.
"""
import hashlib,re,unicodedata
from pathlib import Path

VERSION='gui-kind-rules-1'

def normalize(text):
    # Preserve the original label in observation/logging. Only comparison folds
    # Unicode width, case, spacing and a trailing UI ellipsis.
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip().casefold().removesuffix('...').strip()

ALIASES={
 'file_picker':('Browse files','Choose file','Choose a file','Select file','Select a file','File picker',
     '浏览文件','选择文件','选取文件','ファイルを参照','ファイルを選択','ファイルを選ぶ'),
 'folder_picker':('Browse folders','Choose folder','Choose a folder','Select folder','Select a folder','Folder picker',
     '浏览文件夹','选择文件夹','选取文件夹','フォルダーを参照','フォルダを参照','フォルダーを選択','フォルダを選択','フォルダーを選ぶ'),
 'help_guide':('User guide','User manual','Usage instructions','Help documentation',
     '使用指南','用户手册','帮助文档','ユーザーガイド','操作ガイド','操作マニュアル','使い方'),
 'about_application':('About application','About this app','About this application','Application information','App information',
     '关于应用','关于本应用','应用信息','アプリについて','このアプリについて','アプリ情報'),
}
INDEX={normalize(label):kind for kind,labels in ALIASES.items() for label in labels}
assert sum(len(set(map(normalize,labels))) for labels in ALIASES.values())==len(INDEX)

PATTERNS={
 'file_picker':(
  r'(?:open|show|display|launch) (?:the |a |an )?(?:(?:local|system|native|windows) )?file (?:picker|chooser|selection (?:dialog|window))',
  r'(?:choose|select|pick) (?:a |one |the )?(?:local )?file(?: to attach)?',
  r'(?:打开|显示|唤起)(?:一个)?(?:本地|系统)?文件(?:选择|选取)(?:窗口|对话框|界面|器)',
  r'(?:ローカル|システムの)?ファイル(?:を選ぶ|を選択する)(?:画面|ダイアログ)を(?:開く|表示する)'),
 'folder_picker':(
  r'(?:open|show|display|launch) (?:the |a |an )?(?:(?:local|system|native|windows) )?folder (?:picker|chooser|selection (?:dialog|window))',
  r'(?:choose|select|pick) (?:a |one |the )?(?:local )?folder(?: as the (?:destination|target))?',
  r'(?:打开|显示|唤起)(?:一个)?(?:本地|系统)?文件夹(?:选择|选取)(?:窗口|对话框|界面|器)',
  r'选择(?:一个)?文件夹作为目标位置',
  r'(?:ローカル|システムの)?フォルダー?(?:を選ぶ|を選択する)(?:画面|ダイアログ)を(?:開く|表示する)',
  r'保存先としてフォルダー?を選ぶ'),
 'help_guide':(
  r'(?:open|show|display|read) (?:the |a |an )?(?:user guide|user manual|help documentation|usage instructions)(?: for (?:this|the) (?:app|application))?',
  r'(?:打开|查看|显示)(?:(?:这个|该)?应用的)?(?:使用指南|用户手册|帮助文档)',
  r'(?:(?:この)?アプリの)?(?:使い方|操作方法)を(?:確認する|調べる|見る)',
  r'(?:ユーザーガイド|操作ガイド|操作マニュアル)を(?:開く|表示する)'),
 'about_application':(
  r'(?:open|show|display) (?:the )?(?:about (?:this |the )?(?:app|application)(?: (?:page|dialog))?|(?:app|application) information)',
  r'(?:打开|查看|显示)(?:关于(?:本)?应用(?:的)?(?:页面|窗口)?|应用信息)',
  r'(?:この)?アプリ(?:について|情報)(?:の画面)?を(?:開く|表示する|確認する)'),
}

def intent_kind(intent):
    text=normalize(intent).removesuffix('.').removesuffix('。')
    kinds=[kind for kind,patterns in PATTERNS.items() if any(re.fullmatch(p,text) for p in patterns)]
    return kinds[0] if len(kinds)==1 else None

def control_kind(control):return INDEX.get(normalize(control.name)) if control.role.casefold()=='button' else None

def required_kind(step):
    if step.op!='click' or step.effect not in ('none','local') or not step.target or not step.target.semantic:return None
    return intent_kind(step.intent)

def conflict(required,control):
    observed=control_kind(control)
    return bool(required and observed and required!=observed)

def shortcut(step,controls):
    required=required_kind(step)
    if not required:return None,None
    found=[c for c in controls if control_kind(c)==required]
    if len(found)>1:return required,'ambiguous'
    if len(found)==1:return required,found[0]
    return required,None

def fingerprint():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
