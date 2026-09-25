from jev_client import ROOT
from .examples import query,pred

LABELS={"en":["Draft text","Ready","Save locally","Preview","Clear draft"],"zh":["草稿内容","准备完成","保存到本机","预览","清空草稿"],"ja":["下書き本文","準備完了","この端末に保存","プレビュー","下書きを消去"]}
INTENTS={"en":"Save the draft locally on this device.","zh":"把草稿保存在本机。","ja":"下書きをこの端末に保存してください。"}

def contract(language):
    labels=LABELS[language]
    return {"goal":"Complete the synthetic local draft benchmark.","language":language,
      "target":{"driver":"browser","url":(ROOT/"gui_delegate/fixtures/benchmark.html").as_uri()+"?lang="+language},
      "scope":{"read_roots":[str(ROOT/"gui_delegate/fixtures")],"actions":["fill","check","click"]},
      "inputs":{"draft":{"value":{"en":"Synthetic test & < >\nLine two","zh":"合成测试 & < >\n第二行","ja":"合成テスト & < >\n二行目"}[language]}},
      "steps":[{"id":"fill","intent":"Fill the provided draft text","op":"fill","effect":"local","target":query("textbox",labels[0]),"input_ref":"draft","after":[pred("value","textbox",labels[0],ref="draft")]},
        {"id":"ready","intent":"Mark the draft ready","op":"check","effect":"local","target":query("checkbox",labels[1]),"after":[pred("checked","checkbox",labels[1],True)]},
        {"id":"save","intent":INTENTS[language],"op":"click","effect":"local","target":{"role":"button","name":"__semantic_goal__","group":"Draft actions","semantic":True},"after":[pred("text","status","Result","Saved"),pred("text","status","Count","1")]}],
      "success":[pred("value","textbox",labels[0],ref="draft"),pred("checked","checkbox",labels[1],True),pred("text","status","Result","Saved"),pred("text","status","Count","1")],
      "jev_label_allowlist":labels[2:],"budget":{"seconds":45,"steps":5,"jev_calls":2}}
