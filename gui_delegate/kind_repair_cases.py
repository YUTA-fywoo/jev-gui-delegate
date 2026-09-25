"""Frozen prospective combinations, plus unrelated compatibility cases."""
import random

FAMILIES=[
 ('file_picker',('Display a system file chooser','Select a file…','Select a folder…','Recent files'),('唤起系统文件选取对话框','选取文件…','选取文件夹…','最近使用的文件'),('システムのファイルを選択するダイアログを表示する','ファイルを選ぶ…','フォルダーを選ぶ…','最近使ったファイル')),
 ('folder_picker',('Show a native folder selection dialog','Select a folder…','Select a file…','Recent files'),('显示一个本地文件夹选择界面','浏览文件夹…','浏览文件…','最近使用的文件'),('ローカルフォルダーを選択するダイアログを開く','フォルダを選択…','ファイルを選択…','最近使ったファイル')),
 ('help_guide',('Read the user manual for this app','User manual','Application information','Check for updates'),('查看该应用的用户手册','用户手册','应用信息','检查更新'),('このアプリの操作方法を調べる','操作マニュアル','アプリ情報','更新を確認')),
 ('about_application',('Show the about this application dialog','About this app','Help documentation','Check for updates'),('查看关于本应用的页面','关于本应用','帮助文档','检查更新'),('このアプリについての画面を表示する','このアプリについて','操作ガイド','更新を確認')),
]
COMPAT=[
 ('properties',('Inspect this file’s properties','Properties','Browse files','Browse folders'),('查看选中文件的属性','属性','浏览文件','浏览文件夹'),('選択中のファイルの属性を見る','プロパティ','ファイルを参照','フォルダーを参照')),
 ('release_notes',('Read what changed in the latest release','Release notes','User guide','About application'),('阅读最新版本的变更内容','更新日志','使用指南','关于应用'),('最新バージョンの変更点を読む','更新履歴','ユーザーガイド','アプリについて')),
]

def cases():
    result=[]
    for family,*localized in FAMILIES+COMPAT:
        for language,item in zip(('en','zh','ja'),localized):
            goal,correct,*distractors=item
            for driver in ('browser','windows'):
                for variant in (('normal',) if family in ('properties','release_notes') else ('normal','noise','missing','ambiguous','disabled')):
                    labels=[correct,*distractors];expected=correct;disabled=[]
                    if variant=='missing':labels.remove(correct);expected=None
                    if variant=='disabled':disabled=[correct];expected=None
                    if variant=='ambiguous':labels=[correct,correct,distractors[0]];expected=None
                    if variant=='noise':labels+=dict(en=['Back','More options','Close panel'],zh=['返回','更多选项','关闭面板'],ja=['戻る','その他のオプション','パネルを閉じる'])[language]
                    ident=f'kind-repair-{family}-{language}-{driver}-{variant}';random.Random(ident).shuffle(labels)
                    result.append(dict(id=ident,split='prospective',family=family,language=language,driver=driver,variant=variant,
                        goal=goal,labels=labels,disabled=disabled,expected=expected,risk='local'))
    return result
