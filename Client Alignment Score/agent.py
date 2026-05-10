import json
import os

from openai import OpenAI

from dotenv import load_dotenv


# load environment variables
load_dotenv()


# OpenRouter client
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),

    base_url="https://openrouter.ai/api/v1"
)


SYSTEM_PROMPT = """
You are an expert software business analyst.

Your job is to transform raw client requirements into atomic actionable requirements.

You MUST:

1. Split large multi-purpose requirements into multiple smaller requirements.
2. Separate unrelated ideas into different requirements.
3. Merge duplicate requirements.
4. Rewrite requirements clearly and professionally.
5. Assign a realistic business priority from 1 to 5.

Priority rules:
5 = critical business/core functionality
4 = very important functionality
3 = useful important enhancement
2 = optional improvement
1 = minor enhancement

IMPORTANT:
- A requirement containing multiple ideas MUST be split.
- Do NOT keep long combined requirements.
- Return multiple requirements whenever appropriate.
- Output ONLY valid JSON.
- No markdown.
- No explanations.

Output format:

[
  {
    "text": "requirement text",
    "priority": 5
  }
]
"""


def process_requirements(raw_requirements):

    combined_text = "\n".join([
        r["text"]
        for r in raw_requirements
    ])

    prompt = f"""
Requirements:
{combined_text}
"""

    response = client.chat.completions.create(

        model="openai/gpt-oss-20b:free",

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.2
    )

    content = response.choices[0].message.content.strip()

    # remove markdown if model adds it
    content = content.replace(
        "```json",
        ""
    )

    content = content.replace(
        "```",
        ""
    )

    try:

        processed_requirements = json.loads(
            content
        )

        return processed_requirements

    except Exception as e:

        print("\n===== MODEL RESPONSE =====\n")
        print(content)

        raise e