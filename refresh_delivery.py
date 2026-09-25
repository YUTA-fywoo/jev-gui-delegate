"""Refresh human report and source archive without including any credential store."""
import json
import zipfile
from pathlib import Path
from jev_client import ROOT
from write_manifest import write_manifest

def main():
    from gui_delegate.service import enabled
    if enabled():
        from gui_delegate.delivery import main as gui_delivery
        return gui_delivery()
    manifest_path=write_manifest()
    m=json.loads(manifest_path.read_text("utf-8"))
    all_pass=all(v=="PASS" for v in m["tests"].values())
    lines=["# 本机交付状态","",
        "本阶段全部验收通过：本机安装、真实 Jev API、MCP 认证及 GUI 基础已验证。" if all_pass else "本机安装与验收状态如下；未通过项目不得视为完成。",
        "","| 项目 | 状态 |","|---|---|"]
    lines += ["| "+k+" | "+v+" |" for k,v in m["tests"].items()]
    lines += ["","项目："+str(ROOT),"配置："+m["config_path"],"备份："+str(m["registration_backup"]),
        "交接清单："+str(manifest_path),"实际模型版本："+str(m["api"]["actual_model_version"]),
        "密钥来源："+m["credential"]["source"],"",
        "密钥已保存到当前用户 Windows 凭据管理器；报告不包含密钥值。" if m["credential"]["configured"] else "等待使用 set-key.cmd 保存密钥。",
        "最短真实验收：C:/jev/jev-bridge/verify.cmd",
        "当前对话已实际调用 Jev MCP，无需新开对话。" if not m["new_conversation_required"] else "请新开对话使用注册的 MCP。",
        "本阶段没有让 Jev 接管 GUI，也没有改动 Astra 主模型或登录。阈值校准和连续 GUI 执行器留待下一阶段。"]
    (ROOT/"DELIVERY.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in (".py",".cmd",".json",".md",".lock")]
    files += [ROOT/".env.example",ROOT/".gitignore"]
    files += list((ROOT/"tests").glob("*.py"))+list((ROOT/"tests").glob("*.html"))+list((ROOT/"scripts").glob("*.py"))+list((ROOT/"docs").glob("*.md"))+[ROOT/"docs/llms.txt"]
    files += [p for p in (ROOT/"reports").glob("*.json") if p.name!="pip-install.json"]
    out=ROOT.parent/"jev-bridge-source.zip"
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        archive.comment=b""
        for p in files: archive.write(p,"jev-bridge/"+p.relative_to(ROOT).as_posix())
    print(json.dumps({"all_stage_tests_pass":all_pass,"manifest":str(manifest_path),"source_archive":str(out)},ensure_ascii=False))

if __name__=="__main__":main()
