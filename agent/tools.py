import chainlit as cl
from .state import PlanExecute

@cl.step(name="Create Moodle Course", type="tool")
async def run_moodle_tool_workflow(state: PlanExecute):
    """Creates a course in Moodle based on the provided information."""
    
    # Here you would typically use your Moodle API to create a course
    # For this example, we'll simulate the creation of a course
    # todo api call to create course
    # course_name = state["course_name"]
    # course_description = state["course_description"]
    # course_category = state["course_category"]
    # course_creator = state["course_creator"]
    # course_language = state["course_language"]
    # course_start_date = state["course_start_date"]
    # course_end_date = state["course_end_date"]
    # course_format = state["course_format"]
    # course_visibility = state["course_visibility"]
    # course_enrollment = state["course_enrollment"]
    course_id = "12345"

    print("Creating course...")
    return state