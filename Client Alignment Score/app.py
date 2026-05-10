from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

from alignment import calculate_client_alignment
from agent import process_requirements


app = FastAPI()


class Requirement(BaseModel):
    text: str


class Task(BaseModel):
    text: str


class AlignmentRequest(BaseModel):
    requirements: List[Requirement]
    tasks: List[Task]


@app.post("/alignment-score")
def alignment_score(data: AlignmentRequest):

    raw_requirements = [
        {"text": r.text}
        for r in data.requirements
    ]

    tasks = [
        {"text": t.text}
        for t in data.tasks
    ]

    # AI preprocessing
    processed_requirements = process_requirements(raw_requirements)

    # alignment engine
    result = calculate_client_alignment(
        tasks,
        processed_requirements
    )

    # include AI-generated requirements
    result["processed_requirements"] = (
        processed_requirements
    )

    return result