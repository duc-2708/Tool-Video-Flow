"""Deterministic detail and Vietnamese speech budgets for deep briefs."""
import re
from collections import Counter
from agents.director_numbers import normalized_numbers


def warn_scene(scene,message):
    if scene.review_notes is not None and message not in scene.review_notes.warnings:
        scene.review_notes.warnings.append(message)


def speech_budget(duration):
    return {"min_words":int(duration*2.3*.9+.999),"max_words":int(duration*2.8*1.1),"target_words":round(duration*2.55)}


def validate_script_depth(plan,brief,duration=None):
    from agents.validation_rules import run_rules
    from agents.director import DirectorRequest
    request=DirectorRequest(video_type=plan.video_type or "story",video_format=plan.format,duration_sec=duration or plan.target_duration_sec or plan.duration_sec)
    return run_rules(plan,brief,request)
