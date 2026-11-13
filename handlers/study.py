import logging

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database.db import get_language
from keyboards.menus import main_menu, STUDY_TUTOR_BUTTONS
from services.ai_assistant import generate_reply, AIRateLimited
from services.telegram_formatting import format_telegram_html


logger = logging.getLogger(__name__)
router = Router()


class StudyStates(StatesGroup):
    tutoring = State()


STUDY_WELCOME_MESSAGES = {
    "en": (
        "📖 Welcome to EthioMate AI Tutor!\n\n"
        "Ask me about any subject or topic. I can help you "
        "understand concepts step by step, work through problems, "
        "and prepare for examinations.\n\n"
        "You can ask in English, Amharic or Afaan Oromo.\n"
        "Send /studyexit to leave the tutor."
    ),
    "am": (
        "📖 ወደ EthioMate AI አስተማሪ እንኳን በደህና መጡ!\n\n"
        "ስለ ማንኛውም ትምህርት ወይም ርዕስ ይጠይቁ። "
        "ጽንሰ-ሐሳቦችን በደረጃ እንዲረዱ፣ ችግሮችን እንዲፈቱ "
        "እና ለፈተና እንዲዘጋጁ እረዳዎታለሁ።\n\n"
        "በአማርኛ፣ በእንግሊዝኛ ወይም በአፋን ኦሮሞ መጠየቅ ይችላሉ።\n"
        "/studyexit - ከአስተማሪው ለመውጣት"
    ),
    "om": (
        "📖 Gara Barsiisaa AI EthioMate baga nagaan dhuftan!\n\n"
        "Waa'ee barnootaa fi mata duree kamiyyuu na gaafadhu. "
        "Yaad-rimeewwan tartiibaan akka hubattu, rakkoolee akka hiiktu "
        "fi qormaataaf akka qophooftu si gargaara.\n\n"
        "Afaan Ingiliffaa, Amaaraa ykn Afaan Oromootiin gaafachuu dandeessa.\n"
        "/studyexit - Barsiisaa keessaa ba'i"
    )
}


BILINGUAL_TUTOR_INSTRUCTIONS = """
You are EthioMate AI Tutor, a professional, patient and highly effective
teacher for school, university and independent learners.

YOUR TEACHING MISSION:
Help learners understand concepts deeply, develop problem-solving skills
and prepare confidently for examinations. Teach the reasoning, not just
the final answer.

MANDATORY LANGUAGE POLICY:
Every substantial lesson must contain BOTH:
1. A clear English explanation.
2. A natural, accurate Amharic explanation of the same concepts.

Do not omit the Amharic explanation just because the learner writes
in English, Amharic or Afaan Oromo.
The Amharic section must explain the meaning naturally, not merely
translate technical words mechanically.
Keep important English scientific and technical terms where useful,
and explain their meanings in Amharic.
For a very short follow-up, answer briefly while preserving bilingual
clarity where it is useful.

LESSON STRUCTURE:
Adapt the structure to the question. For a substantial lesson, use
these sections where relevant:

📘 TOPIC
Give the topic and subject when they are known.

🇬🇧 ENGLISH EXPLANATION
Start with a simple definition. Explain what the concept means,
why it matters and how it works. Build from basic ideas to more
advanced understanding.

🇪🇹 በአማርኛ ማብራሪያ
Explain the same important ideas in clear, natural Amharic.
Do not make this section much shorter than the English explanation
when the topic is difficult.

🔍 KEY IDEAS
Highlight the most important facts, terms, relationships or rules.

🧪 WORKED EXAMPLE
Use a realistic example. For mathematics and science, show the
known information, formula, substitution, calculation and final
answer with units where applicable. Explain why each step is taken.
Include an Amharic clarification of difficult reasoning.

🌍 REAL-LIFE CONNECTION
When useful, connect the concept to a familiar everyday situation.
Use Ethiopian examples when relevant, without forcing them.

⚠️ COMMON MISTAKES
Explain likely misunderstandings and how to avoid them.

📝 QUICK REVISION
Summarize the essential points in a few memorable statements.

🎯 PRACTICE QUESTION
For substantial lessons, finish with one useful question that checks
understanding. Do not reveal its answer immediately unless requested.

TEACHING QUALITY:
- Be accurate, detailed and encouraging without sounding childish.
- Use clear language appropriate to the learner's stated grade.
- Explain new vocabulary before relying on it.
- Break complicated processes into numbered steps.
- Use examples that genuinely demonstrate the concept.
- For advanced questions, explain the underlying reasoning.
- For calculations, check arithmetic, signs and units.
- Distinguish established facts from assumptions.
- Never invent curriculum requirements or examination facts.
- If a learner provides a grade, syllabus or textbook context,
  use it to guide the explanation.
- If essential information is missing, ask one focused question.

TELEGRAM PRESENTATION:
- Use short paragraphs and meaningful section headings.
- Use simple Markdown bold headings only when helpful.
- Use ordinary numbered steps and bullet lists.
- Do not use Markdown tables.
- Do not print heading markers such as ###.
- Do not surround ordinary explanations with code formatting.
- Avoid decorative character sequences, excessive emojis and filler.
- Keep formulas readable and preserve necessary scientific symbols.
- Do not produce raw HTML tags.
- Do not output strange escaped newline sequences.
- Do not claim to have attached, generated or displayed an image
  when no image has actually been supplied.

VISUAL TEACHING:
When a diagram would help, explain what the diagram should show
using clear labels and relationships. Do not pretend that a text
description is an actual attached image. The application may add
real educational illustrations and diagrams in a later feature phase.

The learner should finish each substantial lesson understanding
both WHAT the concept means and WHY it works.
"""

STUDY_SYSTEM_INSTRUCTIONS = {
    language: BILINGUAL_TUTOR_INSTRUCTIONS
    for language in ("en", "am", "om")
}


def split_study_message(text, limit=4000):
    """Split long Telegram messages at paragraph or word boundaries."""

    if limit < 1:
        raise ValueError("Message limit must be greater than zero.")

    chunks = []

    while len(text) > limit:
        newline_at = text.rfind("\n", 0, limit + 1)

        if newline_at > 0:
            split_at = newline_at
            separator_length = 1
        else:
            space_at = text.rfind(" ", 0, limit + 1)

            if space_at > 0:
                split_at = space_at
                separator_length = 1
            else:
                split_at = limit
                separator_length = 0

        chunks.append(text[:split_at].strip())
        text = text[split_at + separator_length:].strip()

    if text:
        chunks.append(text)

    return chunks


@router.message(F.text.in_(list(STUDY_TUTOR_BUTTONS.values())))
async def open_study_tutor(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    await state.clear()
    await state.set_state(StudyStates.tutoring)
    await state.update_data(study_history=[])

    await message.answer(STUDY_WELCOME_MESSAGES[language])


@router.message(StudyStates.tutoring, F.text == "/studyexit")
async def exit_study_tutor(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()

    messages = {
        "en": "You have left the AI Tutor.",
        "am": "ከAI አስተማሪው ወጥተዋል።",
        "om": "Barsiisaa AI keessaa baateetta."
    }

    await message.answer(
        messages[language],
        reply_markup=main_menu(language)
    )


@router.message(StudyStates.tutoring, F.text)
async def process_study_question(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    question = message.text.strip()

    if not question:
        return

    data = await state.get_data()
    history = data.get("study_history", [])

    history.append({
        "role": "user",
        "parts": [{"text": question}]
    })

    processing = {
        "en": "⏳ Preparing your lesson...",
        "am": "⏳ ትምህርቱን እያዘጋጀሁ ነው...",
        "om": "⏳ Barnoota qopheessaa jira..."
    }

    errors = {
        "en": "I couldn't prepare the lesson right now. Please try again.",
        "am": "አሁን ትምህርቱን ማዘጋጀት አልቻልኩም። እባክዎ ደግመው ይሞክሩ።",
        "om": "Amma barnoota qopheessuu hin dandeenye. Maaloo irra deebi'i."
    }

    busy = {
        "en": "The AI request limit has been reached temporarily. Please wait a little and try again.",
        "am": "የAI ጥያቄ ገደብ ለጊዜው ደርሷል። እባክዎ ትንሽ ቆይተው ይሞክሩ።",
        "om": "Daangaan gaaffii AI yeroo ammaa ga'ameera. Maaloo yeroo muraasa eeggadhuutii irra deebi'aa yaalaa."
    }

    status = await message.answer(processing[language])

    try:
        answer = await generate_reply(
            history=history,
            language=language,
            system_instruction=STUDY_SYSTEM_INSTRUCTIONS[language]
        )

        history.append({
            "role": "model",
            "parts": [{"text": answer}]
        })

        await state.update_data(study_history=history[-12:])
        await status.delete()

        for chunk in split_study_message(answer):
            await message.answer(
                format_telegram_html(chunk),
                parse_mode=ParseMode.HTML
            )

    except AIRateLimited:
        logger.warning(
            "Study Tutor rate limited for user %s",
            message.from_user.id
        )

        # FSM state and study history are intentionally preserved.
        await status.edit_text(busy[language])

    except Exception:
        logger.exception(
            "Study Tutor request failed for user %s",
            message.from_user.id
        )
        await status.edit_text(errors[language])


@router.message(StudyStates.tutoring)
async def unsupported_study_input(message: Message):
    language = get_language(message.from_user.id)

    messages = {
        "en": "Please send your learning question as text.",
        "am": "እባክዎ የትምህርት ጥያቄዎን በጽሑፍ ይላኩ።",
        "om": "Maaloo gaaffii barnootaa kee barreeffamaan ergi."
    }

    await message.answer(messages[language])
