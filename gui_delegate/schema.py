from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

Op = Literal["read", "wait", "click", "fill", "select", "check", "uncheck", "scroll", "range", "upload", "download", "switch_tab", "close_tab", "context_click", "drag", "key", "copy", "paste", "double_click", "hover", "navigate", "back", "forward", "reload", "new_tab", "screenshot", "export", "logs", "assets", "dialog_accept", "dialog_dismiss", "clipboard_write", "clipboard_read", "mark_deliverable", "mark_handoff", "viewport_set", "viewport_reset"]
# Operations with no ordinary document control, and operations whose proof is a
# local artifact/receipt rather than a changed DOM fingerprint.
PAGE_OPS={'switch_tab','close_tab','navigate','back','forward','reload','new_tab','screenshot','export','logs','assets','dialog_accept','dialog_dismiss','clipboard_write','clipboard_read','mark_deliverable','mark_handoff','viewport_set','viewport_reset'}
NON_DOM_OPS={'read','wait','switch_tab','copy','screenshot','export','logs','assets','clipboard_write','clipboard_read','mark_deliverable','mark_handoff','hover','reload','download'}
Effect = Literal["none", "local", "submit", "send", "publish", "pay", "delete", "overwrite", "account"]

class Query(Strict):
    role: str = Field(min_length=1, max_length=40)
    name: str | None = Field(default=None, max_length=160)
    automation_id: str | None = Field(default=None, max_length=160)
    frame_url: str | None = Field(default=None, max_length=2048)
    group: str | None = Field(default=None,max_length=160)
    semantic: bool = False

class Predicate(Strict):
    surface: str = "main"
    comparison: Literal['eq','ne','gt','ge','lt','le'] = 'eq'
    kind: Literal["exists", "absent", "value", "text", "checked", "url", "file", "tab_count", "attribute"]
    attribute: Literal['scrollTop','scrollLeft','files'] | None = None
    target: Query | None = None
    equals: str | bool | int | None = None
    input_ref: str | None = None

    @model_validator(mode='after')
    def valid_comparison(self):
        if self.comparison!='eq' and self.kind not in ('value','attribute'):raise ValueError('comparison requires value predicate')
        if self.kind=='attribute' and not self.attribute:raise ValueError('attribute name required')
        return self

class InputValue(Strict):
    kind: Literal["text", "path"] = "text"
    value: str = Field(max_length=32000)
    sensitive: bool = False
    pending: bool = False
    captured: bool = False

class BrowserOptions(Strict):
    scroll_x: int = Field(default=0,ge=-4000,le=4000)
    scroll_y: int = Field(default=400,ge=-4000,le=4000)
    full_page: bool = False
    export_format: Literal['page','dom_snapshot','pdf','md','xlsx','csv','docx','pptx','youtube_transcript']='page'
    asset_kinds: list[Literal['font','image','stylesheet','video']] = Field(default_factory=lambda:['image'],max_length=4)
    expected_download_name: str | None = Field(default=None,max_length=240)
    download_directory: str | None = None
    upload_refs: list[str] = Field(default_factory=list,max_length=19)
    allow_close_existing: bool = False
    viewport_width: int | None = Field(default=None,ge=400,le=3840)
    viewport_height: int | None = Field(default=None,ge=300,le=2160)

class Step(Strict):
    surface: str = Field(default="main",pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,48}$")
    intent: str = Field(min_length=1, max_length=300)
    op: Op
    target: Query | None = None
    destination: Query | None = None
    output_ref: str | None = None
    input_ref: str | None = None
    effect: Effect = "none"
    after: list[Predicate] = Field(min_length=1, max_length=8)
    optional_if: Predicate | None = None
    # A semantic request may examine this many observed candidates, never discard a tail silently.
    max_candidates: int = Field(default=12, ge=2, le=24)
    browser_options: BrowserOptions | None = None

class Authorization(Strict):
    step_id: str
    effect: Effect
    target_name: str
    destination: str
    user_instruction: str = Field(min_length=8, max_length=500)

class Scope(Strict):
    programs: list[str] = Field(default_factory=list, max_length=8)
    origins: list[str] = Field(default_factory=list, max_length=20)
    read_roots: list[str] = Field(default_factory=list, max_length=12)
    write_roots: list[str] = Field(default_factory=list, max_length=12)
    actions: list[Op] = Field(min_length=1, max_length=50)

class Budget(Strict):
    steps: int = Field(default=40, ge=1, le=200)
    jev_calls: int = Field(default=8, ge=0, le=30)
    seconds: int = Field(default=180, ge=5, le=900)
    reobservations: int = Field(default=3, ge=0, le=10)
    no_progress: int = Field(default=3, ge=1, le=8)

class Target(Strict):
    driver: Literal["browser", "windows", "unsupported"]
    connection: Literal['isolated', 'official_chrome'] = Field(default='isolated',description='Browser tasks must use official_chrome. Legacy isolated browser requests escalate without launching anything; native Windows ignores this selector.')
    tab_id: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2048)
    hwnd: int | None = Field(default=None, gt=0)
    process_id: int | None = Field(default=None, gt=0)
    executable: str | None = None
    window_title: str | None = Field(default=None, max_length=200)
    headless: bool = Field(default=True,deprecated=True,description="Legacy compatibility only; never launches a browser")
    viewport_width: int = Field(default=1280,ge=400,le=3840)
    viewport_height: int = Field(default=720,ge=300,le=2160)
    device_scale_factor: float = Field(default=1.0,ge=0.5,le=4.0)

    @model_validator(mode='after')
    def complete_identity(self):
        if self.connection=='official_chrome' and (self.driver!='browser' or not self.tab_id):raise ValueError('official Chrome requires browser and explicit tab identity')
        if self.connection=='isolated' and self.tab_id is not None:raise ValueError('tab identity requires official Chrome connection')
        if self.driver=='browser' and not self.url:raise ValueError('browser URL required')
        if self.driver=='windows' and not all((self.hwnd,self.process_id,self.executable,self.window_title)):
            raise ValueError('exact Windows identity required')
        return self

class Contract(Strict):
    version: Literal[1] = 1
    goal: str = Field(min_length=1, max_length=600)
    language: Literal["zh", "ja", "en", "mixed"] = "en"
    target: Target
    targets: dict[str,Target] = Field(default_factory=dict,max_length=7)
    scope: Scope
    inputs: dict[str, InputValue] = Field(default_factory=dict, max_length=40)
    steps: list[Step] = Field(min_length=1, max_length=120)
    success: list[Predicate] = Field(min_length=1, max_length=12)
    stop_conditions: list[Predicate] = Field(default_factory=list, max_length=12)
    authorizations: list[Authorization] = Field(default_factory=list, max_length=20)
    jev_label_allowlist: list[str] = Field(default_factory=list, max_length=120)
    budget: Budget = Field(default_factory=Budget)

    @model_validator(mode="after")
    def valid_refs(self):
        if 'main' in self.targets:raise ValueError('main target is reserved')
        if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',name) for name in self.targets):raise ValueError('invalid surface name')
        surfaces={'main',*self.targets}
        if any(s.surface not in surfaces for s in self.steps):raise ValueError('unknown surface')
        if any(p.surface not in surfaces for p in self.success+self.stop_conditions):raise ValueError('unknown predicate surface')
        if any(v.captured and (v.value or v.pending or v.sensitive) for v in self.inputs.values()):raise ValueError('captured references must start empty')
        ids=[s.id for s in self.steps]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate step ID")
        for s in self.steps:
            if s.op not in self.scope.actions: raise ValueError("unauthorized operation")
            if s.op not in PAGE_OPS and s.target is None: raise ValueError("target required")
            if s.op in ("fill","select","range","upload","download","switch_tab","key","paste","navigate","new_tab","screenshot","export","logs","assets","clipboard_write","clipboard_read") and s.input_ref is None: raise ValueError("input required")
            if s.browser_options and s.browser_options.upload_refs:
                if s.op!='upload' or any(ref not in self.inputs for ref in s.browser_options.upload_refs):raise ValueError('upload file references required')
            if s.op=='drag' and (s.destination is None or s.destination.semantic):raise ValueError('exact drag destination required')
            if s.op!='drag' and s.destination is not None:raise ValueError('only drag accepts a destination')
            if s.op=='copy' and (s.output_ref not in self.inputs or not self.inputs[s.output_ref].captured):raise ValueError('declared captured output required')
            if s.output_ref and s.op!='copy':raise ValueError('only copy can create a captured value')
            if any(p.surface!=s.surface for p in s.after):raise ValueError('step postconditions must use step surface')
            if s.optional_if and s.optional_if.surface!=s.surface:raise ValueError('skip predicate must use step surface')
            for ref in [s.input_ref]+[p.input_ref for p in s.after]+([s.optional_if.input_ref] if s.optional_if else []):
                if ref is not None and ref not in self.inputs: raise ValueError("unknown input reference")
        for p in self.success+self.stop_conditions:
            if p.input_ref is not None and p.input_ref not in self.inputs: raise ValueError("unknown input reference")
        if any(a.step_id not in ids for a in self.authorizations): raise ValueError("unknown authorization step")
        if self.target.driver=="browser" and not self.target.url: raise ValueError("browser URL required")
        if self.target.driver=="windows" and not all((self.target.hwnd,self.target.process_id,self.target.executable,self.target.window_title)):
            raise ValueError("exact Windows identity required")
        return self

class Control(Strict):
    id: str
    role: str
    name: str
    automation_id: str = ""
    frame_url: str = ""
    enabled: bool
    visible: bool
    password: bool = False
    value: str | None = None
    checked: bool | None = None
    attributes: dict[str, str] = Field(default_factory=dict)

class Observation(Strict):
    surface: str = "main"
    sequence: int
    observed_at: float
    fingerprint: str
    location: str
    controls: list[Control]
    tab_count: int = 1

class Action(Strict):
    step_id: str
    op: Op
    control_id: str | None
    fingerprint: str
    observation_sequence: int
    input_ref: str | None = None
    destination_control_id: str | None = None

class Checkpoint(Strict):
    task_id: str
    contract_hash: str
    next_step: int
    completed: list[str]
    phase: Literal["idle", "dispatched", "verified"]
    pending_step: str | None = None
    pending_control_id: str | None = None
    before_fingerprint: str | None = None
    reason: str | None = None

class Result(Strict):
    status: Literal["running", "completed", "escalated", "needs_confirmation", "paused", "cancelled", "blocked", "failed"]
    task_id: str
    completed: list[str]
    remaining: list[str]
    evidence_refs: list[str]
    usage: dict
    escalation_reason: str | None
    resume_token: str
    verification: list[dict] = Field(default_factory=list)
    escalation_context: dict | None = None
    routing: dict = Field(default_factory=dict)
    tab_cleanup: dict = Field(default_factory=dict)

class DecisionOverride(Strict):
    step_id: str
    control_id: str
    observation_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

class Resume(Strict):
    resume_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    wait_seconds: int = Field(default=35, ge=0, le=40)
    continue_task: bool = False
    user_released_control: bool = False
    input_updates: dict[str,str] = Field(default_factory=dict,max_length=20)
    decision_override: DecisionOverride | None = None

class Cancel(Strict):
    resume_token: str = Field(pattern=r"^[a-f0-9]{64}$")

class Diagnose(Strict):
    resume_token: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
