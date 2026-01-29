# LTFS Conversational Call Flow – Diagrams

## 1. End-to-end call flow (high level)

```mermaid
flowchart TB
    subgraph Client
        User[User / Frontend]
    end

    subgraph Backend
        WS[WebSocket Handler]
        FM[flow_manager]
        CF[conversational_flow]
        TR[transcript_retrieval]
        Prompt[config.prompt]
        LLM[Gemini / call_gemini]
        Session[(Session Store)]
    end

    User <-->|audio / messages| WS
    WS -->|get_question_text / process_answer| FM
    FM -->|process_conversational_response| CF
    CF -->|build_context_for_turn| CF
    CF -->|get_examples_for_turn| TR
    TR -->|Excel transcripts| TR
    CF -->|CONVERSATIONAL_PROMPT| Prompt
    CF -->|full_prompt| LLM
    LLM -->|bot_response, extracted_data, next_action| CF
    CF -->|update session| Session
    CF -->|response| FM
    FM -->|text / phase| WS
    WS -->|TTS / summary / closing| User
```

---

## 2. Context engineering (per turn)

*Each time the user speaks, the system curates what goes into the model’s context window.*

```mermaid
flowchart LR
    subgraph Possible["Possible context to give model"]
        Doc1[Doc – Excel transcripts]
        Doc2[Doc – Transcript examples]
        Inst[Comprehensive instructions\nconfig.prompt]
        State[Session state\ncurrent_data, missing_info, stage]
        Hist[Message history\nlast_bot_response, generated_summary]
        UIn[User message]
    end

    subgraph Curation["Curation (each turn)"]
        Phase[Infer phase from stage]
        Retrieve[get_examples_for_turn\nsession, user_input, phase, k=3]
        Assemble[build_context_for_turn\nsystem prompt + examples_block\n+ session summary + user_input]
    end

    subgraph ContextWindow["Context window (actual input)"]
        Sys[System prompt]
        Ex[Doc 1, Doc 2, Doc 3\nretrieved examples]
        Ctx[Current conversation context]
        Msg[Customer response]
    end

    subgraph Model["Model"]
        Gen[Gemini]
    end

    subgraph Output["Output"]
        Bot[Assistant message]
        Act[next_action / end_call]
    end

    Doc1 --> Retrieve
    Doc2 --> Retrieve
    State --> Phase
    Phase --> Retrieve
    UIn --> Retrieve
    Inst --> Assemble
    Retrieve --> Assemble
    State --> Assemble
    Hist --> Assemble
    UIn --> Assemble

    Assemble --> Sys
    Assemble --> Ex
    Assemble --> Ctx
    Assemble --> Msg

    Sys --> Gen
    Ex --> Gen
    Ctx --> Gen
    Msg --> Gen

    Gen --> Bot
    Gen --> Act
    Act -->|continue| State
    Bot --> Hist
```

---

## 3. Conversation phase flow (session state)

```mermaid
stateDiagram-v2
    [*] --> Conversation

    Conversation --> Conversation : user speaks\n(process_conversational_response)\ncontext engineered each turn

    Conversation --> Summary : all info collected\nprovide_summary=true

    Summary --> Conversation : user says wrong / edit
    Summary --> Closing : user confirms (yes)

    Conversation --> Closing : end_call\n(wrong_person / no_loan / etc.)

    Closing --> [*] : get_closing_text, disconnect
```

---

## 4. Single-turn pipeline (context → response)

*What runs inside `process_conversational_response` for one user message.*

```mermaid
sequenceDiagram
    participant FM as flow_manager
    participant CF as conversational_flow
    participant TR as transcript_retrieval
    participant Prompt as config.prompt
    participant LLM as gemini_client

    FM->>CF: process_conversational_response(user_input, session, customer_name)
    CF->>CF: get_conversation_stage(session)
    CF->>CF: get_missing_information(session)
    CF->>CF: build_context_for_turn(...)

    CF->>TR: get_examples_for_turn(session, user_input, phase, k=3)
    TR-->>CF: List[TranscriptExample]

    CF->>Prompt: CONVERSATIONAL_PROMPT
    CF->>CF: Assemble full_prompt = prompt + examples_block + session context + user_input

    CF->>LLM: call_gemini(full_prompt)
    LLM-->>CF: { bot_response, extracted_data, next_action, ... }

    CF->>CF: Update session with extracted_data
    CF-->>FM: { bot_response, next_action, provide_summary, ... }
```

---

## 5. Transcript retrieval (context source)

```mermaid
flowchart TB
    Excel["LTFS Survey calls – 10 transcripts\nfor each categories.xlsx"]
    Load["_load_examples()\nopenpyxl, once per process"]
    Index["In-memory list of\nTranscriptExample"]
    Turn["get_examples_for_turn\n(session, user_input, phase, k=3)"]
    Score["Score by token overlap\n+ phase/sheet bias"]
    Top["Return top-k examples"]

    Excel --> Load
    Load --> Index
    Index --> Turn
    Turn --> Score
    Score --> Top
    Top -->|examples_block| build_context_for_turn
```

---

## 6. Context-catching tools (optional)

When `USE_CONTEXT_TOOLS=true` in env, the model can **call tools** to fetch context before responding:

- **get_transcript_examples(phase, query, max_results)** – returns relevant call snippets from the Excel transcripts.
- **get_session_summary()** – returns current session state (identity, loan, payment fields, stage).

Flow: prompt + tools → model → (optional) tool_call → execute_tool → append result to contents → model again → … → final JSON. Implemented in `llm/context_tools.py` and `llm/gemini_client.call_gemini_with_tools`.

---

## How to view

- **VS Code**: Install “Mermaid” or “Markdown Preview Mermaid Support” and open this file in preview.
- **GitHub**: Push this file and view the repo; GitHub renders Mermaid in `.md` files.
- **Online**: Copy a code block into [mermaid.live](https://mermaid.live) to edit or export as PNG/SVG.
