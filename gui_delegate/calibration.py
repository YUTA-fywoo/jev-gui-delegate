"""Finite real-Jev/real-browser threshold evaluation. Never labels fixtures production calibration."""
import argparse,html,itertools,json,math,random,time
from pathlib import Path
from jev_client import ROOT,JevClient
from .controller import Controller,THRESHOLDS,EXITS
from .schema import Contract,Checkpoint
from .security import Stop

DATA={
 'en':[
  ('Keep the draft only on this computer',['Preview draft','Save locally','Clear draft'],1),
  ('Show the next results page',['Previous page','Next page','Refresh results'],1),
  ('Make additional details visible',['Hide details','Expand details','Compact view'],1),
  ('Switch the display to Japanese',['English','日本語','中文'],1),
  ('Open the settings menu without changing any preference',['Close menu','Open menu','Reset view'],1),
  ('Show a preview without storing edits',['Save locally','Preview draft','Clear draft'],1)],
 'zh':[
  ('把草稿保留在这台设备上',['预览草稿','保存到本机','清空草稿'],1),
  ('查看后一页的结果',['上一页','下一页','刷新结果'],1),
  ('显示更多详细信息',['收起详情','展开详情','紧凑视图'],1),
  ('将显示语言改为日语',['English','日本語','中文'],1),
  ('仅打开设置菜单，不修改选项',['关闭菜单','打开菜单','重置视图'],1),
  ('只预览草稿，暂时不保存',['保存到本机','预览草稿','清空草稿'],1)],
 'ja':[
  ('下書きをこの端末だけに保存する',['プレビュー','端末に保存','下書きをクリア'],1),
  ('検索結果の次のページを表示する',['前のページ','次のページ','結果を更新'],1),
  ('詳細な情報を表示する',['詳細を閉じる','詳細を開く','簡易表示'],1),
  ('表示言語を日本語にする',['English','日本語','中文'],1),
  ('設定を変更せずにメニューだけを開く',['メニューを閉じる','メニューを開く','表示をリセット'],1),
  ('保存せずに下書きを確認する',['端末に保存','プレビュー','下書きをクリア'],1)]}

def cases():
    result=[]
    for language,items in DATA.items():
        for split in ('train','validation'):
            for number in range(12):
                goal,labels,index=items[number%len(items)];labels=list(labels);correct=labels[index]
                missing=number in (4,10)
                if missing:labels.remove(correct)
                random.Random(language+split+str(number)).shuffle(labels)
                # Holdout changes candidate order and distractor context, not invented labels.
                if split=='validation':labels+=['Back' if language=='en' else '返回' if language=='zh' else '戻る']
                result.append({'id':f'{language}-{split}-{number}','language':language,'split':split,'goal':goal,
                    'labels':labels,'correct_label':None if missing else correct,'application':'isolated_browser_fixture','risk':'local'})
    return result

def eligible(row,threshold):
    a=row.get('answer')
    if not a or a['choice'] in EXITS:return False
    values=sorted(a['probabilities'].values(),reverse=True)
    return (a['probabilities'][a['choice']]>=threshold['probability'] and a['confidence']>=threshold['confidence']
       and values[0]-values[1]>=threshold['margin'])

def wilson(success,n):
    if not n:return None
    z=1.959963984540054;p=success/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-half),min(1,center+half)]

def summarize(rows):
    report={}
    for lang in DATA:
        train=[r for r in rows if r['language']==lang and r['split']=='train'];test=[r for r in rows if r['language']==lang and r['split']=='validation']
        options=[]
        for p,c,m in itertools.product((.80,.85,.90,.93,.95,.97,.99,.999),(.65,.75,.85,.9,.95,.99),(.10,.15,.25,.40,.60)):
            t={'probability':p,'confidence':c,'margin':m}
            accepted=[r for r in train if eligible(r,t)]
            if accepted and all(r['model_correct'] for r in accepted):options.append((len(accepted),t))
        chosen=max(options,key=lambda x:x[0])[1] if options else None
        accepted=[r for r in test if chosen and eligible(r,chosen)]
        correct=sum(r['model_correct'] for r in accepted)
        interval=wilson(correct,len(accepted))
        report[lang]={'training_samples':len(train),'validation_samples':len(test),'suggested_thresholds':chosen,
          'validation_accepted':len(accepted),'validation_correct_among_accepted':correct,'validation_wrong_among_accepted':len(accepted)-correct,
          'coverage':len(accepted)/len(test) if test else 0,'accepted_correctness_95pct_wilson_interval':interval,
          'correct_absence_exits':sum(r['correct_label'] is None and r['model_correct'] for r in test),
          'actual_verified_actions':sum(r['action_verified'] for r in test),'actual_wrong_actions':sum(r['wrong_action'] for r in test),
          'production_calibrated':False,'reason':'Small synthetic sample; no representative production labels. Statistical interval describes only this fixture sample.'}
    return report

if __name__=='__main__':
    raise SystemExit('Historical Edge collector retired. Existing cases/statistics remain importable; use official Chrome task contracts for new browser evidence.')
