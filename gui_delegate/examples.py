from urllib.parse import urlsplit

def query(role,name):return {"role":role,"name":name}
def pred(kind,role,name,equals=None,ref=None):
    p={"kind":kind,"target":query(role,name)}
    if equals is not None:p["equals"]=equals
    if ref is not None:p["input_ref"]=ref
    return p

def workflow(url="http://127.0.0.1:8000/",tab_id="__new__"):
    steps=[]
    def add(ident,op,role,name,after,ref=None,intent=None,semantic=False):
        s={"id":ident,"intent":intent or f"{op} {name}","op":op,"target":query(role,name),"effect":"local","after":[after]}
        if semantic:s["target"]["semantic"]=True
        if ref:s["input_ref"]=ref
        steps.append(s)
    add("name","fill","textbox","姓名",pred("value","textbox","姓名",ref="name"),"name")
    add("memo","fill","textbox","メモ",pred("value","textbox","メモ",ref="memo"),"memo")
    add("language","select","combobox","Language",pred("value","combobox","Language","日本語"),"language")
    add("agree","check","checkbox","同意",pred("checked","checkbox","同意",True))
    add("uncheck","uncheck","checkbox","同意",pred("checked","checkbox","同意",False))
    add("recheck","check","checkbox","同意",pred("checked","checkbox","同意",True))
    add("menu","click","button","Open menu",pred("exists","button","Compact view"))
    add("compact","click","button","Compact view",pred("text","status","Mode","Compact"))
    add("page","click","button","Next page",pred("text","cell","Row","Page 2"))
    add("wizard","click","button","Next dialog",pred("exists","button","Finish wizard"))
    add("finish","click","button","Finish wizard",pred("text","status","Wizard state","Wizard done"))
    add("save","click","button","Store the edited draft on this device",pred("text","status","Saved state","Saved locally"),intent="Save this draft locally on the device. Do not preview or clear it.",semantic=True)
    steps[-1]["target"]["group"]="Draft actions"
    return {"goal":"Complete a synthetic local draft workflow without external side effects.","language":"mixed",
      "target":{"driver":"browser","connection":"official_chrome","tab_id":str(tab_id),"url":url},
      "scope":{"programs":[],"origins":[urlsplit(url).scheme+"://"+urlsplit(url).netloc],"read_roots":[],"write_roots":[],"actions":sorted({s["op"] for s in steps})},
      "inputs":{"name":{"value":"合成测试 张三"},"memo":{"value":"日本語のテスト\n中文第二行 & < > \" ' \\ $"},"language":{"value":"日本語"}},
      "steps":steps,"success":[pred("text","status","Saved state","Saved locally"),pred("text","status","Save count","1"),pred("value","textbox","メモ",ref="memo")],
      "jev_label_allowlist":["Open menu","Compact view","Next page","Virtual item","Next dialog","Save locally","Preview","Clear draft"],
      "budget":{"seconds":180,"steps":30,"jev_calls":3}}

if __name__=="__main__":
    import json
    print(json.dumps(workflow(),ensure_ascii=False,indent=2))
