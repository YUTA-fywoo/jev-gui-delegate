"""Fresh intent families, frozen before confirmation of the two release profiles."""
import random

FAMILIES=[
('selectall',('Select every item currently shown','Select all','Clear selection','Invert selection'),('选中当前显示的全部项目','全选','取消选择','反向选择'),('表示中の項目をすべて選ぶ','すべて選択','選択を解除','選択を反転')),
('deselect',('Remove the selection without deleting any item','Clear selection','Delete selected items','Invert selection'),('取消选中状态，保留所有项目','取消选择','删除选中项目','反向选择'),('項目を削除せずに選択状態を解除する','選択を解除','選択した項目を削除','選択を反転')),
('wrap',('Wrap long lines inside the text pane','Word wrap','Line numbers','Horizontal scroll'),('让长行文字在面板内自动换行','自动换行','显示行号','水平滚动'),('長い行をテキスト欄の幅で折り返す','折り返し表示','行番号を表示','横スクロール')),
('case',('Make the search distinguish uppercase from lowercase','Match case','Whole words','Regular expression'),('让搜索区分大写字母和小写字母','区分大小写','全字匹配','正则表达式'),('検索で大文字と小文字を区別する','大文字と小文字を区別','単語単位で検索','正規表現')),
('fitwidth',('Scale the page to fit the available horizontal space','Fit width','Fit height','Actual size'),('按可用的横向空间调整页面显示比例','适合宽度','适合高度','实际大小'),('利用できる横幅にページの倍率を合わせる','幅に合わせる','高さに合わせる','実際のサイズ')),
('dark',('Use a dark background for this preview only','Dark theme','Light theme','Follow system'),('只把当前预览的背景切换成深色','深色主题','浅色主题','跟随系统'),('このプレビューだけ背景を暗くする','ダークテーマ','ライトテーマ','システムに合わせる')),
('mute',('Keep the preview playing but silence its audio','Mute audio','Pause playback','Stop playback'),('继续播放预览，但关闭声音','静音','暂停播放','停止播放'),('プレビューの再生を続けたまま音を消す','ミュート','一時停止','再生を停止')),
('rotate',('Turn the preview a quarter turn clockwise','Rotate clockwise','Rotate counterclockwise','Flip horizontally'),('把预览顺时针旋转四分之一圈','顺时针旋转','逆时针旋转','水平翻转'),('プレビューを時計回りに四分の一回転する','右に回転','左に回転','左右反転')),
]

def cases():
    result=[]
    for family,*localized in FAMILIES:
        for language,item in zip(('en','zh','ja'),localized):
            goal,correct,*distractors=item
            for driver in ('browser','windows'):
                for variant in ('normal','noise','missing'):
                    labels=[correct,*distractors];expected=correct
                    if variant=='missing':labels.remove(correct);expected=None
                    if variant=='noise':labels+=dict(en=['Back','More options','Close panel'],zh=['返回','更多选项','关闭面板'],ja=['戻る','その他のオプション','パネルを閉じる'])[language]
                    ident=f'confirmation-{family}-{language}-{driver}-{variant}'
                    random.Random(ident).shuffle(labels)
                    result.append(dict(id=ident,split='confirmation',family=family,language=language,driver=driver,variant=variant,
                        goal=goal,labels=labels,disabled=[],expected=expected,risk='local'))
    return result
