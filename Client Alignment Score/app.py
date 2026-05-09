from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

from alignment import calculate_client_alignment

app = FastAPI()


class Requirement(BaseModel):
    text: str
    priority: int


class Task(BaseModel):
    text: str


class AlignmentRequest(BaseModel):
    requirements: List[Requirement]
    tasks: List[Task]


@app.post("/alignment-score")
def alignment_score(data: AlignmentRequest):

    requirements = [{"text": r.text, "priority": r.priority} for r in data.requirements]
    tasks = [{"text": t.text} for t in data.tasks]

    result = calculate_client_alignment(tasks, requirements)

    return result