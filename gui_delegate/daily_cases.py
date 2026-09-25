"""Authored semantic truth; split by intent family before any model evaluation."""
import random,hashlib,json

# Each row: split, family, then (goal, correct label, two distractors) in en/zh/ja.
FAMILIES=[
('train','preview',('Inspect the draft without saving it','Preview draft','Save locally','Clear draft'),('先查看草稿效果，暂时不保存','预览草稿','保存到本机','清空草稿'),('保存せずに下書きを確認する','プレビュー','端末に保存','下書きをクリア')),
('train','next',('Go to the following results page','Next page','Previous page','Refresh results'),('查看后一页的搜索结果','下一页','上一页','刷新结果'),('検索結果の次のページを見る','次のページ','前のページ','結果を更新')),
('train','expand',('Reveal the currently folded details','Expand details','Collapse details','Compact view'),('展开当前折叠的详细信息','展开详情','收起详情','紧凑视图'),('折りたたまれた詳細を表示する','詳細を展開','詳細を折りたたむ','簡易表示')),
('train','grid',('Arrange the visible items as a grid','Grid view','List view','Details view'),('把项目按网格排列显示','网格视图','列表视图','详细信息'),('項目を格子状に並べる','グリッド表示','一覧表示','詳細表示')),
('train','zoomreset',('Return the zoom level to its original size','Reset zoom','Zoom in','Zoom out'),('恢复最初的缩放大小','重置缩放','放大','缩小'),('表示倍率を元の大きさに戻す','ズームをリセット','拡大','縮小')),
('train','find',('Search for text within the current document','Find in document','Find files','Replace text'),('在当前文档内查找文字','文档内查找','查找文件','替换文字'),('今の文書の中で文字を探す','文書内を検索','ファイルを検索','文字を置換')),
('train','recent',('Show documents opened recently','Recent files','All files','Pinned files'),('查看最近打开过的文档','最近使用的文件','所有文件','固定的文件'),('最近開いた文書を表示する','最近使ったファイル','すべてのファイル','固定したファイル')),
('train','folder',('Choose a folder as the destination','Choose folder','Choose file','New document'),('选择一个文件夹作为目标位置','选择文件夹','选择文件','新建文档'),('保存先としてフォルダーを選ぶ','フォルダーを選択','ファイルを選択','新しい文書')),
('train','history',('Display the list of finished downloads','Download history','Browsing history','Bookmarks'),('查看已经完成的下载列表','下载记录','浏览记录','书签'),('完了したダウンロードの一覧を見る','ダウンロード履歴','閲覧履歴','ブックマーク')),
('train','undo',('Reverse the most recent edit','Undo','Redo','Reset all'),('撤回刚才的那一步编辑','撤销','重做','全部重置'),('直前の編集操作を取り消す','元に戻す','やり直し','すべてリセット')),
('train','refresh',('Reload the currently displayed results','Refresh results','Next page','Clear results'),('重新载入当前结果','刷新结果','下一页','清空结果'),('表示中の結果を読み込み直す','結果を更新','次のページ','結果を消去')),
('train','sortup',('Sort the item names alphabetically from A to Z','Name ascending','Name descending','Date ascending'),('按名称从前到后排序','名称升序','名称降序','日期升序'),('名前を昇順で並べ替える','名前の昇順','名前の降順','日付の昇順')),
('holdout','previous',('Go back one page of results','Previous page','Next page','First page'),('回到前一页结果','上一页','下一页','第一页'),('結果を一つ前のページに戻す','前のページ','次のページ','最初のページ')),
('holdout','collapse',('Hide the expanded detailed section','Collapse details','Expand details','Close document'),('收起已展开的详情区域','收起详情','展开详情','关闭文档'),('開いている詳細欄を折りたたむ','詳細を折りたたむ','詳細を展開','文書を閉じる')),
('holdout','list',('Show items in a vertical list instead of tiles','List view','Tile view','Grid view'),('将项目改为竖向列表而不是平铺','列表视图','平铺视图','网格视图'),('項目をタイルではなく縦の一覧にする','一覧表示','タイル表示','グリッド表示')),
('holdout','zoomout',('Make the displayed content appear smaller','Zoom out','Zoom in','Reset zoom'),('把显示的内容缩小一点','缩小','放大','重置缩放'),('表示している内容を小さくする','縮小','拡大','ズームをリセット')),
('holdout','clearquery',('Empty only the search box','Clear search','Clear results','Reset form'),('只清空搜索框中的内容','清空搜索','清空结果','重置表单'),('検索欄だけを空にする','検索をクリア','結果を消去','フォームをリセット')),
('holdout','properties',('Inspect information about the selected file','File properties','Open file','Folder options'),('查看选中文件的详细属性','文件属性','打开文件','文件夹选项'),('選択したファイルの属性を確認する','ファイルのプロパティ','ファイルを開く','フォルダーオプション')),
('holdout','parent',('Navigate to the enclosing folder','Up one folder','Previous location','Home folder'),('进入当前文件夹的上一级目录','上一级文件夹','上一个位置','主文件夹'),('現在のフォルダーの一つ上へ移動する','親フォルダーへ','前の場所','ホームフォルダー')),
('holdout','redo',('Reapply the edit that was just undone','Redo','Undo','Repeat search'),('恢复刚刚撤销的编辑操作','重做','撤销','再次搜索'),('取り消した編集をもう一度適用する','やり直し','元に戻す','再検索')),
('holdout','sortdown',('Sort names from Z to A','Name descending','Name ascending','Date descending'),('按名称从后到前排序','名称降序','名称升序','日期降序'),('名前を降順に並べ替える','名前の降順','名前の昇順','日付の降順')),
('holdout','printpreview',('Inspect how the document will look on paper without printing','Print preview','Print now','Page setup'),('只预览纸张上的效果，先不打印','打印预览','立即打印','页面设置'),('印刷せずに用紙上の見え方を確認する','印刷プレビュー','今すぐ印刷','ページ設定')),
('holdout','browse',('Open the local file picker','Browse files','Browse folders','Recent files'),('打开本地文件选择窗口','浏览文件','浏览文件夹','最近使用的文件'),('ローカルファイルを選ぶ画面を開く','ファイルを参照','フォルダーを参照','最近使ったファイル')),
('holdout','cancel',('Leave this dialog without applying its changes','Cancel','Apply','Confirm'),('退出这个对话框，不应用其中的更改','取消','应用','确认'),('変更を適用せずにこのダイアログを閉じる','キャンセル','適用','確認')),
('holdout','hidden',('Make hidden files visible in the listing','Show hidden files','Hide files','Show file extensions'),('在列表中显示隐藏文件','显示隐藏文件','隐藏文件','显示文件扩展名'),('一覧に隠しファイルを表示する','隠しファイルを表示','ファイルを隠す','拡張子を表示')),
('holdout','sidebar',('Reveal the navigation sidebar','Show sidebar','Hide sidebar','Show toolbar'),('显示导航侧边栏','显示侧边栏','隐藏侧边栏','显示工具栏'),('ナビゲーション用サイドバーを表示する','サイドバーを表示','サイドバーを隠す','ツールバーを表示')),
('holdout','help',('Open the user guide for this application','User guide','About application','Check for updates'),('打开这个应用的使用指南','使用指南','关于应用','检查更新'),('このアプリの使い方を確認する','ユーザーガイド','アプリについて','更新を確認')),
('holdout','newtab',('Open an additional blank browser tab','New tab','New window','Reopen closed tab'),('打开一个新的空白浏览器标签页','新建标签页','新建窗口','重新打开关闭的标签页'),('空白のブラウザータブを追加する','新しいタブ','新しいウィンドウ','閉じたタブを復元')),
('holdout','first',('Jump to the beginning of the paginated results','First page','Previous page','Last page'),('跳到分页结果的最开头','第一页','上一页','最后一页'),('ページ分けされた結果の先頭に移動する','最初のページ','前のページ','最後のページ')),
('holdout','exitfull',('Return from fullscreen to the normal window','Exit fullscreen','Enter fullscreen','Minimize window'),('退出全屏并恢复普通窗口','退出全屏','进入全屏','最小化窗口'),('全画面表示から通常のウィンドウに戻す','全画面表示を終了','全画面表示にする','ウィンドウを最小化')),
]

def cases():
    out=[]
    for split,family,*localized in FAMILIES:
        for language,item in zip(('en','zh','ja'),localized):
            goal,correct,*distractors=item
            for driver in ('browser','windows'):
                for variant in (('normal','missing') if split=='train' else ('normal','noise','missing','ambiguous','disabled')):
                    labels=[correct,*distractors];expected=correct;disabled=[]
                    if variant=='missing':labels.remove(correct);expected=None
                    if variant=='ambiguous':labels=[correct,correct,distractors[0]];expected=None
                    if variant=='disabled':disabled=[correct];expected=None
                    if variant=='noise':labels+=dict(en=['Back','More options','Close panel'],zh=['返回','更多选项','关闭面板'],ja=['戻る','その他のオプション','パネルを閉じる'])[language]
                    ident=f'{split}-{family}-{language}-{driver}-{variant}'
                    random.Random(ident).shuffle(labels)
                    out.append({'id':ident,'split':split,'family':family,'language':language,'driver':driver,'variant':variant,
                        'goal':goal,'labels':labels,'disabled':disabled,'expected':expected,'risk':'local'})
    return out

def dataset_hash(dataset):return hashlib.sha256(json.dumps(dataset,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
