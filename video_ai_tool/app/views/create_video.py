"""One screen to start a fresh project or resume a durable pipeline."""
import streamlit as st
from pipeline.run_all_jobs import PipelineJobs
from app.views.ai_video import ai_video_jobs
from editor.timeline import confined
from pipeline.projects import read_json


@st.cache_resource
def pipeline_jobs():
    return PipelineJobs()


def read_ui_state(project, snapshot=None):
    """A torn/locked checkpoint must not break a Streamlit rerun."""
    if snapshot and snapshot.get("state") and (project is None or snapshot.get("project") == str(project)):
        return snapshot["state"]
    if project is not None:
        try:
            return read_json(confined(project, "run_state.json"), allow_stale=True)
        except (OSError, ValueError):
            pass
    if snapshot and (project is None or snapshot.get("project") == str(project)):
        return snapshot.get("state")
    return None


def render(settings, project, topic, debug, diagnostics):
    from app.views import create_video_hub

    return create_video_hub.render(settings, project, topic, debug, diagnostics)
