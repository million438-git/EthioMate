import json
import re

from services.ai_assistant import generate_reply


QUIZ_SYSTEM_INSTRUCTIONS = """
You are an experienced secondary-school teacher and examination question writer.
Create accurate, challenging but fair multiple-choice questions.
Return only valid JSON. Do not use Markdown fences or additional commentary.
Each question must have exactly four options and exactly one correct answer.
Provide clear explanations in English and Amharic.
Never invent facts or ambiguous answers.
"""


def _normalize_text(value):
    """Normalize text for duplicate detection without changing displayed text."""
    return " ".join(value.casefold().split())


def parse_quiz_response(raw_text, expected_count):
    """Parse and validate the structured quiz returned by the AI."""

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("The quiz generator returned an empty response.")

    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("The quiz generator returned invalid JSON.") from exc

    questions = data.get("questions") if isinstance(data, dict) else None

    if not isinstance(questions, list) or len(questions) != expected_count:
        raise ValueError("The generated quiz has an unexpected number of questions.")

    required_text_fields = (
        "question_en",
        "question_am",
        "explanation_en",
        "explanation_am",
    )

    validated = []
    seen_questions_en = set()
    seen_questions_am = set()

    for number, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError(f"Question {number} has an invalid format.")

        for field in required_text_fields:
            if not isinstance(question.get(field), str) or not question[field].strip():
                raise ValueError(f"Question {number} is missing {field}.")

        question_en_key = _normalize_text(question["question_en"])
        question_am_key = _normalize_text(question["question_am"])

        if question_en_key in seen_questions_en:
            raise ValueError(f"Question {number} duplicates an earlier English question.")

        if question_am_key in seen_questions_am:
            raise ValueError(f"Question {number} duplicates an earlier Amharic question.")

        seen_questions_en.add(question_en_key)
        seen_questions_am.add(question_am_key)

        for field in ("options_en", "options_am"):
            options = question.get(field)
            if (
                not isinstance(options, list)
                or len(options) != 4
                or not all(isinstance(option, str) and option.strip() for option in options)
            ):
                raise ValueError(f"Question {number} must have four valid {field} options.")

            normalized_options = [_normalize_text(option) for option in options]
            if len(set(normalized_options)) != 4:
                raise ValueError(f"Question {number} contains duplicate {field} options.")

        correct_index = question.get("correct_index")
        if type(correct_index) is not int or correct_index not in range(4):
            raise ValueError(f"Question {number} has an invalid correct answer.")

        validated.append({
            "question_en": question["question_en"].strip(),
            "question_am": question["question_am"].strip(),
            "options_en": [item.strip() for item in question["options_en"]],
            "options_am": [item.strip() for item in question["options_am"]],
            "correct_index": correct_index,
            "explanation_en": question["explanation_en"].strip(),
            "explanation_am": question["explanation_am"].strip(),
        })

    return validated


async def _generate_quiz_batch(
    subject, topic, difficulty, count, existing_questions=None
):
    prompt = f"""
Create exactly {count} multiple-choice questions.

Subject: {subject}
Topic: {topic}
Difficulty: {difficulty}

Requirements:

1. SUBJECT AND CURRICULUM RELEVANCE
- Use only concepts relevant to the requested subject and topic.
- Write questions appropriate for the requested difficulty level.
- Target serious secondary-school, Ethiopian curriculum, and national examination preparation where relevant.
- Do not introduce unrelated topics or assume facts that were not provided.
- Do not invent scientific facts, formulas, constants, historical details, or numerical data.

2. QUESTION QUALITY AND COGNITIVE DEPTH
- Assess conceptual understanding, application, analytical reasoning, and problem-solving.
- Include conceptual understanding questions, application questions, and problem-solving questions where appropriate to the subject.
- Avoid testing memorization alone.
- Use clear, precise, natural question wording.
- Make every question unambiguous and fair.
- Avoid unnecessary trick questions and confusing negative wording.
- Use realistic situations and examples when they improve understanding.
- Match the complexity of calculations and reasoning to the requested difficulty.

3. ANSWER OPTIONS
- Provide exactly four answer options for every question.
- Provide one and only one unambiguously correct answer.
- Create plausible distractors based on common misconceptions or likely mistakes.
- Make options mutually distinct and consistent in style, grammar, and level of detail.
- Do not use "all of the above" or "none of the above".
- Do not make the correct answer obvious through its length, wording, or formatting.
- Do not repeat any answer option within a question.

4. ENGLISH AND AMHARIC ACCURACY
- Write every question in clear English and natural Amharic.
- Translate the full meaning accurately; do not translate word-for-word when that would sound unnatural.
- Keep the four English and Amharic options in the same order and with the same meaning.
- The correct_index must identify the same correct option in both languages.
- Use appropriate scientific and academic terminology in both languages.
- Do not omit important information when translating.

5. EXPLANATIONS AND LEARNING VALUE
- Explain the reasoning behind the correct answer in English and Amharic.
- Make explanations educational, accurate, and understandable.
- For calculation questions, show the relevant formula, essential reasoning steps, and correct units.
- For conceptual questions, explain the underlying principle clearly.
- Keep both language explanations consistent in meaning.
- Avoid explanations that merely repeat the correct option.

6. VARIETY AND ORIGINALITY
- Do not repeat questions or test exactly the same idea with slightly changed wording.
- Vary the reasoning and application required across the question set.
- Avoid duplicate or equivalent answer options.
- Do not sacrifice accuracy or clarity just to create variety.

7. STRICT OUTPUT FORMAT
- Return exactly the requested number of questions.
- Each question must contain all seven required fields in the JSON structure below.
- Use an integer correct_index from 0 to 3.
- Return only valid JSON.
- Do not include Markdown fences, introductions, conclusions, or answers outside the JSON structure.

Return this exact JSON structure:
{{
  "questions": [
    {{
      "question_en": "Question in English",
      "question_am": "Question in Amharic",
      "options_en": ["Option A", "Option B", "Option C", "Option D"],
      "options_am": ["አማራጭ ሀ", "አማራጭ ለ", "አማራጭ ሐ", "አማራጭ መ"],
      "correct_index": 0,
      "explanation_en": "Explanation in English",
      "explanation_am": "ማብራሪያ በአማርኛ"
    }}
  ]
}}
"""

    existing_questions = existing_questions or []

    if existing_questions:
        excluded = [
            {
                "question_en": item["question_en"],
                "question_am": item["question_am"],
            }
            for item in existing_questions
        ]

        prompt += (
            "\\n\\nPREVIOUSLY GENERATED QUESTIONS — DO NOT REPEAT:"
            "\\n"
            + json.dumps(excluded, ensure_ascii=False)
            + "\\nCreate entirely different questions testing different "
              "concepts or applications."
        )

    # Retry duplicate questions without weakening validation.
    max_attempts = 3

    existing_en = {
        _normalize_text(item["question_en"])
        for item in existing_questions
    }
    existing_am = {
        _normalize_text(item["question_am"])
        for item in existing_questions
    }

    for attempt in range(max_attempts):
        attempt_prompt = prompt

        if attempt:
            attempt_prompt += (
                "\\n\\nIMPORTANT: Your previous response contained "
                "duplicate questions. Generate completely different "
                "questions. Do not paraphrase or repeat any earlier question."
            )

        response = await generate_reply(
            history=[
                {
                    "role": "user",
                    "parts": [{"text": attempt_prompt}],
                }
            ],
            language="en",
            system_instruction=QUIZ_SYSTEM_INSTRUCTIONS,
        )

        try:
            questions = parse_quiz_response(response, count)
        except ValueError as exc:
            if (
                "duplicates an earlier" in str(exc)
                and attempt < max_attempts - 1
            ):
                continue
            raise

        duplicate_found = any(
            _normalize_text(item["question_en"]) in existing_en
            or _normalize_text(item["question_am"]) in existing_am
            for item in questions
        )

        if not duplicate_found:
            return questions

    raise ValueError(
        "Could not generate a complete quiz without duplicate questions "
        "after three attempts. Please try again."
    )

async def generate_quiz(subject, topic, difficulty, count):
    """
    Generate a complete quiz in batches of up to five questions.

    Validate the combined result again so duplicates across batches
    are rejected before the quiz is returned to the handler.
    """

    if type(count) is not int or not 1 <= count <= 15:
        raise ValueError("Quiz question count must be between 1 and 15.")

    batch_size = 5
    all_questions = []

    for start in range(0, count, batch_size):
        batch_count = min(batch_size, count - start)

        batch_questions = await _generate_quiz_batch(
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            count=batch_count,
            existing_questions=all_questions,
        )

        all_questions.extend(batch_questions)

    combined_response = json.dumps(
        {"questions": all_questions},
        ensure_ascii=False,
    )

    return parse_quiz_response(combined_response, count)
