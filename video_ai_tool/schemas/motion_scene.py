"""Strict presentation contracts with a bounded normalization boundary."""

from copy import deepcopy

from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel, Field, ValidationError, model_validator

from schemas.base import StrictModel

from schemas.visual import VisualData,VisualBeat



SceneType=Literal[
    'versus_scale',
    'bar_grow',
    'gauge',
    'ring',
    'line_draw',
    'flow_chain',
    'magnifier_check',
    'funnel_filter',
    'checklist',
    'terminal_type',
    'timeline_march',
    'stack_cards',
    'network_nodes',
    'text_focus',
    'stat_number',
    'bar_compare',
    'container_fill',
    'hub_spoke',
    'mock_ui_window',
    'versus_split',
    'line_chart_draw',
    'terminal_typing',
    'code_card',
    'timeline',
    'funnel',
    'progress_tracker',
    'source_badge',
    'icon_tile',
    'chat_bubble_poll',
    'gauge_ring',
    'slot_counter',
    'strike_replace',
    'gauge_needle',
    'odometer',
    'bar_race',
    'thermometer',
    'battery_fill',
    'glass_fill',
    'balance_scale',
    'tug_of_war',
    'vs_flip_cards',
    'before_after_wipe',
    'conveyor_belt',
    'domino_chain',
    'pipeline_pipes',
    'dice_roll',
    'lock_unlock',
    'shield_hit',
    'traffic_light',
    'orbit_system',
    'layered_onion',
    'stack_pile',
    'puzzle_snap',
    'chat_thread',
    'mock_card_swipe',
    'form_fill_submit',
    'terminal_command_run',
    'before_after_split',
    'timeline_milestones',
    'map_location_pin',
    'profile_dossier',
    'document_page_flip',
    'camera_surveillance_scan',
    'evidence_board',
    'network_graph',
    'countdown_timer',
    'courtroom_balance',
    'code_terminal_window',
    'quote_dialog_card'
]





def normalize_motion_payload(value, model, *, origin='llm'):

    """Strip extra presentation keys before strict validation, not fact fields.



    Notices are also returned separately: older in-memory model classes may

    not yet declare repair_notes. Never put input values into these notices.

    """

    notes=[]

    def walk(raw, schema, path):

        if isinstance(raw,BaseModel): raw=raw.model_dump(mode='python')

        if not isinstance(raw,dict): return deepcopy(raw)

        result={}

        for name,item in raw.items():

            if name not in schema.model_fields:

                label=name if isinstance(name,str) and name.isidentifier() and len(name)<=64 else '<khóa lạ>'

                group=3 if origin=='llm' else 2

                notes.append(f'[illustration_extra, nhóm {group}] {path}.{label}: bỏ khóa ngoài hợp đồng ({origin}); không dùng giá trị đó.')

                continue

            annotation=schema.model_fields[name].annotation

            origin_type=get_origin(annotation)

            args=get_args(annotation)

            if origin_type is list and args:

                element=args[0]

                result[name]=[walk(v,element,f'{path}.{name}[{i}]') for i,v in enumerate(item)] if isinstance(element,type) and issubclass(element,BaseModel) and isinstance(item,list) else deepcopy(item)

            else:

                nested=next((t for t in (annotation,*args) if isinstance(t,type) and issubclass(t,BaseModel)),None)

                if nested and isinstance(item,(dict,BaseModel)):

                    result[name]=walk(item,nested,path+'.'+name)

                else: result[name]=deepcopy(item)

        return result

    data=walk(value,model,'visual_plan')

    if isinstance(data,dict) and 'repair_notes' in model.model_fields:

        existing=data.get('repair_notes',[])

        if isinstance(existing,list) and all(isinstance(n,str) for n in existing):

            if existing or notes: data['repair_notes']=list(dict.fromkeys([*existing,*notes]))

    return data,notes





class SceneCamera(StrictModel):

    kind: Literal['push_in','pull_out','pan_left','pan_right']='push_in'

    amount: float=Field(default=.06,ge=.04,le=.08)





class SceneAnnotation(StrictModel):

    type: Literal['strike','check','cross','underline','circle_highlight','stamp','question','arrow','tag','pencil'] = 'strike'

    target: str = ''

    at_sec: float | None = None

    at_phrase: str = ''

    text: str = ''





class MotionScenePlan(StrictModel):

    scene_type: SceneType='text_focus'

    theme: Literal['neon_dark','paper_brand','whiteboard_sketch','studio','cong-nghe','tin-tuc','kinh-doanh'] | None = None

    layout: Literal['center_hero','split_2','stack_3','grid_4','timeline_h','text_focus'] | None = None

    zone: Literal['top','middle','bottom','left','right','center'] | None = None

    evidence: str | None = None

    no_numbers: bool = False

    anchor: str | None = None

    central_metaphor: str | None = None

    metaphor_state: str | None = None

    data: VisualData=Field(default_factory=VisualData)

    beats: list[VisualBeat]=Field(default_factory=list)

    camera: SceneCamera=Field(default_factory=SceneCamera)

    mascot_state: Literal['idle','point','shrug','surprised','think']='idle'

    repair_notes: list[str]=Field(default_factory=list,exclude_if=lambda v:not v)

    annotations: list[SceneAnnotation]=Field(default_factory=list,exclude_if=lambda v:not v)

    motion_recipe: str | None = Field(default=None, exclude_if=lambda v: v is None)

    variant_index: int | None = Field(default=None, exclude_if=lambda v: v is None)

    transition: str | None = Field(default=None, exclude_if=lambda v: v is None)



    @model_validator(mode='wrap')

    @classmethod

    def recover_presentation(cls,value,handler,info):

        clean,notes=normalize_motion_payload(value,cls,origin=(info.context or {}).get('motion_origin','llm'))

        try:

            return handler(clean)

        except (ValidationError,TypeError,ValueError) as error:

            # Exactly one local repair of invalid optional components. Essential

            # script/event/fact schemas never pass through this boundary.

            repaired=dict(clean) if isinstance(clean,dict) else {}

            fields=sorted({str(e['loc'][0]) for e in error.errors(include_input=False) if e['loc']}) if isinstance(error,ValidationError) else []

            for name in fields: repaired.pop(name,None)

            if 'data' in fields: repaired['scene_type']='text_focus'

            notes=list(dict.fromkeys([*notes,'[illustration_data, nhóm 2] visual_plan: sửa thành phần sai kiểu về mặc định ('+(', '.join(fields) or type(error).__name__)+').']))

            if 'repair_notes' in cls.model_fields: repaired['repair_notes']=notes

            try: return handler(repaired)

            except Exception:

                fallback={'scene_type':'text_focus'}

                if 'repair_notes' in cls.model_fields:

                    fallback['repair_notes']=[*notes,'[illustration_data, nhóm 2] Không sửa được visual_plan; dùng text_focus.']

                # Even the fallback must match the actual loaded class.

                return handler({k:v for k,v in fallback.items() if k in cls.model_fields})



