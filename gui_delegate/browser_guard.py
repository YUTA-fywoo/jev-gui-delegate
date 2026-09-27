"""Browser Use's page-key + selected-target guard, adapted to read-only CUA.

The upstream checks document/form state and the chosen node's semantics. A
recommendation elsewhere on a page is not part of the chosen control's identity.
"""
from .security import digest

FORM_ROLES={'textbox','searchbox','combobox','checkbox','radio','switch','slider'}
TARGET_ATTRS=('tag','type','dom_path','context','neighborhood','group','href','submit','target',
              'readonly','expanded','selected','form_action','form_context')

def action_guard(observation,control_id):
    selected=next((c for c in observation.controls if c.id==control_id),None)
    if selected is None:return None
    target=[selected.id,selected.role,selected.name,selected.automation_id,
            selected.frame_url,selected.visible,selected.enabled,selected.password,
            selected.value,selected.checked,
            {k:selected.attributes.get(k,'') for k in TARGET_ATTRS}]
    forms=[[c.id,c.role,c.value,c.checked,c.enabled,c.attributes.get('readonly','')]
           for c in observation.controls if c.role in FORM_ROLES]
    return digest([observation.location,target,forms])
